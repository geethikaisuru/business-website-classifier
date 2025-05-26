import os
import requests
import time
import csv
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
import http.client

class GooglePlacesBusinessChecker:
    def __init__(self):
        load_dotenv()
        self.gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = "gemini-2.0-flash-lite"
        self.businesses_without_websites = []
        self.places_api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
        if not self.places_api_key:
            raise Exception("GOOGLE_PLACES_API_KEY not set in .env file.")

    def _deep_sanitize(self, obj):
        if isinstance(obj, dict):
            return {k: self._deep_sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_sanitize(v) for v in obj]
        elif obj is None:
            return ""
        else:
            return str(obj)

    def search_businesses_in_area(self, location, business_type="", max_results=50):
        print(f"[PLACES] Searching for: {business_type or 'All businesses'} in {location}")
        # Geocode location to lat/lng
        geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={requests.utils.quote(location)}&key={self.places_api_key}"
        print(f"[PLACES][DEBUG] Geocoding URL: {geocode_url}")
        geo_resp = requests.get(geocode_url).json()
        print(f"[PLACES][DEBUG] Geocoding raw response: {json.dumps(geo_resp, indent=2)}")
        print(f"[PLACES][DEBUG] Geocoding status: {geo_resp.get('status')}")
        if geo_resp.get('status') != 'OK' or not geo_resp.get('results'):
            print(f"[PLACES][ERROR] Could not geocode location. Status: {geo_resp.get('status')}")
            if 'error_message' in geo_resp:
                print(f"[PLACES][ERROR] Geocoding error message: {geo_resp['error_message']}")
            return []
        latlng = geo_resp['results'][0]['geometry']['location']
        lat, lng = latlng['lat'], latlng['lng']
        print(f"[PLACES] Geocoded to: {lat}, {lng}")
        # Search for places
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lng}",
            "radius": 5000,  # 5km radius
            "type": business_type if business_type else None,
            "key": self.places_api_key
        }
        params = {k: v for k, v in params.items() if v is not None}
        businesses = []
        next_page_token = None
        while len(businesses) < max_results:
            if next_page_token:
                params['pagetoken'] = next_page_token
                time.sleep(2)  # Google requires a short wait for next page
            resp = requests.get(url, params=params).json()
            for result in resp.get('results', []):
                businesses.append({
                    'name': result.get('name'),
                    'place_id': result.get('place_id'),
                    'vicinity': result.get('vicinity'),
                    'maps_url': f"https://www.google.com/maps/place/?q=place_id:{result.get('place_id')}"
                })
                if len(businesses) >= max_results:
                    break
            next_page_token = resp.get('next_page_token')
            if not next_page_token:
                break
        print(f"[PLACES] Found {len(businesses)} businesses.")
        return businesses[:max_results]

    def get_business_detailed_info(self, business):
        # Get details for a business using Place Details API
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": business['place_id'],
            "fields": "name,website,formatted_phone_number,formatted_address,url,review,user_ratings_total,types,geometry,photos,editorial_summary",
            "key": self.places_api_key
        }
        resp = requests.get(url, params=params).json()
        result = resp.get('result', {})
        links = []
        if result.get('website'):
            links.append({'url': result['website'], 'text': 'Official Website'})
        phones = [result.get('formatted_phone_number')] if result.get('formatted_phone_number') else []
        text_snippet = result.get('editorial_summary', {}).get('overview', '')
        return {
            'name': business['name'],
            'maps_url': business['maps_url'],
            'links': links,
            'phones': phones,
            'text_snippet': text_snippet
        }

    def classify_businesses_with_gemini(self, businesses_batch):
        prompt = (
            "You are an expert at analyzing Google Maps business listings to determine if a business has an official website. "
            "You will be given a list of businesses, each with their name, Google Maps URL, any links found (including the API 'website' field), phone numbers, and a text snippet.\n\n"
            "A business HAS_WEBSITE if:\n"
            "- There is a link to an official business website (not just social media, review sites, or third-party platforms)\n"
            "- The website is clearly related to the business (not a generic, unrelated, or placeholder site)\n"
            "- The link is not just to Facebook, Instagram, TripAdvisor, Booking.com, or similar\n"
            "- The website is not a Google Maps, Google Sites, or Google Business Profile page\n"
            "- If you are unsure, classify as NO_WEBSITE (be conservative)\n\n"
            "A business has NO_WEBSITE if:\n"
            "- There are only social media links (Facebook, Instagram, etc.)\n"
            "- There are only phone numbers, addresses, or Google Maps links\n"
            "- There are only third-party platforms like Yelp, TripAdvisor, Booking.com, etc.\n"
            "- There is no clear website reference or domain link\n"
            "- If you are unsure, classify as NO_WEBSITE\n\n"
            "Here are the businesses to analyze:\n\n"
        )
        for i, business in enumerate(businesses_batch, 1):
            name = self._deep_sanitize(business.get('name'))
            maps_url = self._deep_sanitize(business.get('maps_url'))
            links = business.get('links')
            if links is None:
                links = []
            sanitized_links = self._deep_sanitize(links)
            phones = business.get('phones')
            if phones is None:
                phones = []
            sanitized_phones = self._deep_sanitize(phones)
            text_snippet = self._deep_sanitize(business.get('text_snippet'))
            prompt += f"""
Business {i}: {name}
Google Maps URL: {maps_url}
Links found: {json.dumps(sanitized_links, indent=2)}
Phone numbers: {sanitized_phones}
Text snippet: {text_snippet[:500]}...
---
"""
        prompt += (
            "\nPlease respond in this exact JSON format:\n{\n  \"classifications\": [\n    {\"business_name\": \"Business Name\", \"status\": \"HAS_WEBSITE\", \"reason\": \"Brief explanation\"},\n    {\"business_name\": \"Business Name\", \"status\": \"NO_WEBSITE\", \"reason\": \"Brief explanation\"}\n  ]\n}\n\nOnly include the JSON response, no other text."
        )
        max_retries = 3
        for attempt in range(max_retries):
            try:
                contents = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)],
                    ),
                ]
                generate_content_config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
                response_text = ""
                for chunk in self.gemini_client.models.generate_content_stream(
                    model=self.model,
                    contents=contents,
                    config=generate_content_config,
                ):
                    response_text += chunk.text
                try:
                    json_start = response_text.find('{')
                    json_end = response_text.rfind('}') + 1
                    json_text = response_text[json_start:json_end]
                    result = json.loads(json_text)
                    return result['classifications']
                except json.JSONDecodeError as e:
                    print(f"[PLACES][ERROR] Error parsing JSON response: {e}")
                    print(f"[PLACES][ERROR] Raw response: {response_text}")
                    return []
            except (requests.exceptions.ConnectionError, http.client.RemoteDisconnected) as e:
                wait_time = 2 ** attempt
                print(f"[PLACES][WARN] Connection error (attempt {attempt+1}/{max_retries}): {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            except Exception as e:
                print(f"[PLACES][ERROR] Error calling Gemini API: {e}")
                return []
        print("[PLACES][ERROR] Failed to get response from Gemini API after multiple retries. Skipping this batch.")
        return []

    def save_results_to_file(self, filename="places_businesses_without_websites.txt"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Businesses Without Websites (Classified by AI, Places API)\n")
                f.write("=" * 60 + "\n\n")
                for i, business in enumerate(self.businesses_without_websites, 1):
                    f.write(f"{i}. {business['name']}\n")
                    f.write(f"   Google Maps: {business['maps_url']}\n")
                    if 'reason' in business:
                        f.write(f"   AI Analysis: {business['reason']}\n")
                    f.write("\n")
            print(f"[PLACES] Results saved to {filename}")
            print(f"[PLACES] Found {len(self.businesses_without_websites)} businesses without websites")
        except Exception as e:
            print(f"[PLACES][ERROR] Error saving file: {e}")

    def save_results_to_csv(self, filename="places_businesses_without_websites.csv"):
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Business Name', 'Google Maps URL', 'AI Analysis'])
                for business in self.businesses_without_websites:
                    writer.writerow([
                        business['name'],
                        business['maps_url'],
                        business.get('reason', 'No analysis available')
                    ])
            print(f"[PLACES] CSV results saved to {filename}")
        except Exception as e:
            print(f"[PLACES][ERROR] Error saving CSV: {e}")

    def run_search(self, location, business_type="", max_results=50, batch_size=10):
        print("Starting Google Places business website checker (AI for all businesses, conservative)...")
        print(f"Location: {location}")
        print(f"Business type: {business_type or 'All businesses'}")
        print(f"Batch size: {batch_size} (for AI calls)")
        print("-" * 60)
        businesses = self.search_businesses_in_area(location, business_type, max_results)
        if not businesses:
            print("No businesses found. Try a different search term or location.")
            return
        print(f"Found {len(businesses)} businesses to analyze")
        print("-" * 60)
        print("Gathering detailed business information...")
        detailed_businesses = []
        for i, business in enumerate(businesses, 1):
            print(f"Getting details for business {i}/{len(businesses)}: {business['name']}")
            detailed_info = self.get_business_detailed_info(business)
            detailed_businesses.append(detailed_info)
        print("-" * 60)
        print(f"Sending all {len(detailed_businesses)} businesses to AI for classification...")
        # Process all businesses in batches
        for i in range(0, len(detailed_businesses), batch_size):
            batch = detailed_businesses[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(detailed_businesses) + batch_size - 1) // batch_size
            print(f"AI Processing batch {batch_num}/{total_batches} ({len(batch)} businesses)")
            classifications = self.classify_businesses_with_gemini(batch)
            for classification in classifications:
                if classification['status'] == 'NO_WEBSITE':
                    for business in batch:
                        if business['name'] == classification['business_name']:
                            business['reason'] = classification['reason']
                            self.businesses_without_websites.append(business)
                            print(f"✓ No website (AI): {business['name']} - {classification['reason']}")
                            break
                else:
                    print(f"✗ Has website (AI): {classification['business_name']}")
            time.sleep(2)
        print("-" * 60)
        print(f"Analysis complete!")
        print(f"Total businesses analyzed: {len(detailed_businesses)}")
        print(f"Businesses without websites: {len(self.businesses_without_websites)}")
        self.save_results_to_file()
        self.save_results_to_csv() 