import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urlencode
import csv
import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

class GoogleMapsBusinessChecker:
    def __init__(self):
        self.session = requests.Session()
        # Use a realistic user agent to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.businesses_without_websites = []
        
        # Initialize Gemini client
        self.gemini_client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        self.model = "gemma-3n-e4b-it"
    
    def search_businesses_in_area(self, location, business_type=""):
        """
        Search for businesses in a specific area
        location: e.g., "New York, NY" or "Downtown Los Angeles"
        business_type: e.g., "restaurants", "shops", "services" (optional)
        """
        query = f"{business_type} in {location}" if business_type else location
        
        # Google Maps search URL
        base_url = "https://www.google.com/maps/search/"
        search_url = base_url + query.replace(" ", "+")
        
        print(f"Searching for businesses in: {location}")
        print(f"Search URL: {search_url}")
        
        try:
            response = self.session.get(search_url)
            response.raise_for_status()
            
            # Parse the HTML response
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find business listings (this is a simplified approach)
            business_links = soup.find_all('a', {'data-value': True})
            
            businesses_found = []
            for link in business_links[:50]:  # Get more results for batch processing
                business_name = link.get_text(strip=True)
                business_url = "https://www.google.com" + link.get('href', '')
                
                if business_name and len(business_name) > 2:
                    businesses_found.append({
                        'name': business_name,
                        'maps_url': business_url
                    })
            
            return businesses_found
            
        except requests.RequestException as e:
            print(f"Error searching for businesses: {e}")
            return []
    
    def get_business_detailed_info(self, business_name, maps_url):
        """
        Get detailed information about a business from its Google Maps page
        """
        try:
            time.sleep(1)  # Small delay to be respectful
            
            response = self.session.get(maps_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract all text content
            page_text = soup.get_text()
            
            # Extract all links from the page
            links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                link_text = link.get_text(strip=True)
                if href and (href.startswith('http') or 'www.' in href or '.com' in href or '.org' in href):
                    links.append({
                        'url': href,
                        'text': link_text
                    })
            
            # Extract phone numbers, addresses, and other contact info
            contact_info = []
            phone_pattern = r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})'
            phones = re.findall(phone_pattern, page_text)
            
            return {
                'name': business_name,
                'maps_url': maps_url,
                'links': links,
                'phones': phones,
                'text_snippet': page_text[:1000]  # First 1000 chars for context
            }
            
        except requests.RequestException as e:
            print(f"Error getting details for {business_name}: {e}")
            return {
                'name': business_name,
                'maps_url': maps_url,
                'links': [],
                'phones': [],
                'text_snippet': ""
            }
    
    def classify_businesses_with_gemini(self, businesses_batch):
        """
        Use Gemini AI to classify multiple businesses at once
        """
        # Prepare the prompt with business information
        prompt = """You are analyzing Google Maps business listings to identify which businesses DO NOT have websites.

Please analyze the following businesses and classify each one as either "HAS_WEBSITE" or "NO_WEBSITE".

A business HAS_WEBSITE if:
- There are links to official business websites (not just social media)
- URLs containing the business domain or clear website references
- "Website" buttons or links are mentioned
- Clear references to business websites in the text

A business has NO_WEBSITE if:
- Only social media links (Facebook, Instagram, etc.)
- Only phone numbers, addresses, or Google Maps links
- No clear website references or domain links
- Only third-party platforms like Yelp, but no official website

Here are the businesses to analyze:

"""
        
        for i, business in enumerate(businesses_batch, 1):
            prompt += f"""
Business {i}: {business['name']}
Google Maps URL: {business['maps_url']}
Links found: {json.dumps(business['links'], indent=2)}
Phone numbers: {business['phones']}
Text snippet: {business['text_snippet'][:500]}...
---
"""
        
        prompt += """

Please respond in this exact JSON format:
{
  "classifications": [
    {"business_name": "Business Name", "status": "HAS_WEBSITE", "reason": "Brief explanation"},
    {"business_name": "Business Name", "status": "NO_WEBSITE", "reason": "Brief explanation"}
  ]
}

Only include the JSON response, no other text."""
        
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="text/plain",
            )
            
            # Collect the full response
            response_text = ""
            for chunk in self.gemini_client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            ):
                response_text += chunk.text
            
            # Parse the JSON response
            try:
                # Clean up the response to extract JSON
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                json_text = response_text[json_start:json_end]
                
                result = json.loads(json_text)
                return result['classifications']
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON response: {e}")
                print(f"Raw response: {response_text}")
                return []
                
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return []
    
    def save_results_to_file(self, filename="businesses_without_websites.txt"):
        """
        Save businesses without websites to a text file
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Businesses Without Websites (Classified by AI)\n")
                f.write("=" * 60 + "\n\n")
                
                for i, business in enumerate(self.businesses_without_websites, 1):
                    f.write(f"{i}. {business['name']}\n")
                    f.write(f"   Google Maps: {business['maps_url']}\n")
                    if 'reason' in business:
                        f.write(f"   AI Analysis: {business['reason']}\n")
                    f.write("\n")
            
            print(f"Results saved to {filename}")
            print(f"Found {len(self.businesses_without_websites)} businesses without websites")
            
        except Exception as e:
            print(f"Error saving file: {e}")
    
    def save_results_to_csv(self, filename="businesses_without_websites.csv"):
        """
        Save results to CSV format for easier processing
        """
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
            
            print(f"CSV results saved to {filename}")
            
        except Exception as e:
            print(f"Error saving CSV: {e}")
    
    def run_search(self, location, business_type="", max_results=100, batch_size=10):
        """
        Main function to run the complete search process
        """
        print("Starting Google Maps business website checker with AI classification...")
        print(f"Location: {location}")
        print(f"Business type: {business_type or 'All businesses'}")
        print(f"Batch size: {batch_size} businesses per AI call")
        print("-" * 60)
        
        # Check if API key is set
        if not os.environ.get("GEMINI_API_KEY"):
            print("ERROR: Please set your GEMINI_API_KEY environment variable")
            print("Example: export GEMINI_API_KEY='your-api-key-here'")
            return
        
        # Search for businesses
        businesses = self.search_businesses_in_area(location, business_type)
        
        if not businesses:
            print("No businesses found. Try a different search term or location.")
            return
        
        # Limit results
        businesses = businesses[:max_results]
        print(f"Found {len(businesses)} businesses to analyze")
        print("-" * 60)
        
        # Get detailed info for each business
        print("Gathering detailed business information...")
        detailed_businesses = []
        for i, business in enumerate(businesses, 1):
            print(f"Getting details for business {i}/{len(businesses)}: {business['name']}")
            detailed_info = self.get_business_detailed_info(business['name'], business['maps_url'])
            detailed_businesses.append(detailed_info)
        
        print("-" * 60)
        print("Analyzing businesses with AI...")
        
        # Process businesses in batches
        for i in range(0, len(detailed_businesses), batch_size):
            batch = detailed_businesses[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(detailed_businesses) + batch_size - 1) // batch_size
            
            print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} businesses)")
            
            classifications = self.classify_businesses_with_gemini(batch)
            
            # Process classifications
            for classification in classifications:
                if classification['status'] == 'NO_WEBSITE':
                    # Find the corresponding business
                    for business in batch:
                        if business['name'] == classification['business_name']:
                            business['reason'] = classification['reason']
                            self.businesses_without_websites.append(business)
                            print(f"✓ No website: {business['name']} - {classification['reason']}")
                            break
                else:
                    print(f"✗ Has website: {classification['business_name']}")
            
            # Small delay between batches
            time.sleep(2)
        
        print("-" * 60)
        print(f"Analysis complete!")
        print(f"Total businesses analyzed: {len(detailed_businesses)}")
        print(f"Businesses without websites: {len(self.businesses_without_websites)}")
        
        # Save results
        self.save_results_to_file()
        self.save_results_to_csv()

# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check if GEMINI_API_KEY is set
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY is not set in environment or .env file.")
        exit(1)

    print("\n==== Google Maps Business Website Checker ====")
    location = input("Enter location (default: Nugegoda, Sri Lanka): ").strip() or "Nugegoda, Sri Lanka"
    max_results = input("How many businesses to analyze? (default: 50): ").strip()
    batch_size = input("Batch size per AI call? (default: 10): ").strip()
    
    try:
        max_results = int(max_results) if max_results else 50
    except ValueError:
        max_results = 50
    try:
        batch_size = int(batch_size) if batch_size else 10
    except ValueError:
        batch_size = 10

    checker = GoogleMapsBusinessChecker()
    checker.run_search(location, max_results=max_results, batch_size=batch_size)
    
    print("\nSummary:")
    print(f"Location: {location}")
    print(f"Total businesses analyzed: {max_results}")
    print(f"Batch size: {batch_size}")
    print(f"Results saved to businesses_without_websites.txt and businesses_without_websites.csv")
    print("\nProgram finished!")