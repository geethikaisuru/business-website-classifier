import streamlit as st
import os
from main_places_api import GooglePlacesBusinessChecker
import time

st.set_page_config(page_title="No Site Business Finder - NSBF", layout="centered")
st.markdown("""
<style>
.footer-link { color: #2d5be3; text-decoration: underline; font-style: italic; }
.footer { text-align: center; margin-top: 1.5em; color: #2d5be3; font-size: 1rem; }
.status-green { color: #228B22; font-weight: bold; }
.status-red { color: #B22222; font-weight: bold; }
.code-log {background: #eaf0fa; border-radius: 6px; padding: 0.5em 1em; font-family: monospace; font-size: 1em; max-height: 350px; overflow-y: auto;}
</style>
<script>
window.addEventListener('DOMContentLoaded', function() {
  var logBox = document.getElementById('log-box');
  if (logBox) { logBox.scrollTop = logBox.scrollHeight; }
});
</script>
""", unsafe_allow_html=True)

st.title("No Site Business Finder - NSBF 🕵️‍♂️")
st.markdown('<div style="font-size:1.2em; color:#2d5be3; margin-bottom:1em;">Find Businesses that don\'t have websites in a region.</div>', unsafe_allow_html=True)

with st.form("input_form"):
    col1, col2 = st.columns([2, 2])
    with col1:
        location = st.text_input("📍 Location", value="Nugegoda, Sri Lanka")
        max_results = st.number_input("🔢 Max Results", min_value=1, max_value=100, value=50)
        batch_size = st.number_input("📦 Batch Size", min_value=1, max_value=50, value=10)
    with col2:
        gemini_key = os.environ.get("GEMINI_API_KEY")
        places_key = os.environ.get("GOOGLE_PLACES_API_KEY")
        gemini_status = f'<span class="status-green">✅ Found</span>' if gemini_key else f'<span class="status-red">❌ Not Found</span>'
        places_status = f'<span class="status-green">✅ Found</span>' if places_key else f'<span class="status-red">❌ Not Found</span>'
        st.markdown(f"Gemini API Key: {gemini_status}", unsafe_allow_html=True)
        st.markdown(f"Places API Key: {places_status}", unsafe_allow_html=True)
    submitted = st.form_submit_button("🚀 Analyse with Places API")

log_area = st.empty()
progress_bar = st.empty()
notification_area = st.empty()

output_files = [
    ("places_businesses_without_websites.txt", "Text Output (.txt)"),
    ("places_businesses_without_websites.csv", "CSV Output (.csv)")
]

if submitted:
    if not gemini_key:
        notification_area.error("❌ ERROR: GEMINI_API_KEY is not set in environment or .env file.")
    elif not places_key:
        notification_area.error("❌ ERROR: GOOGLE_PLACES_API_KEY is not set in environment or .env file.")
    else:
        checker = GooglePlacesBusinessChecker()
        import builtins
        orig_print = print
        log_lines = []
        def print_to_log(*args, **kwargs):
            msg = ' '.join(str(a) for a in args)
            log_lines.append(msg)
            # Use markdown with a div for auto-scroll
            log_html = f'<div id="log-box" class="code-log">' + '<br>'.join(log_lines[-100:]) + '</div>'
            log_area.markdown(log_html, unsafe_allow_html=True)
            orig_print(*args, **kwargs)
        builtins.print = print_to_log
        try:
            notification_area.info("⏳ Analysis started! Please wait...")
            for i in range(5):
                progress_bar.progress((i+1)/5, text=f"Preparing... {20*(i+1)}%")
                time.sleep(0.2)
            progress_bar.progress(0, text="Running analysis...")
            checker.run_search(location, max_results=int(max_results), batch_size=int(batch_size))
            progress_bar.progress(1.0, text="Analysis complete!")
            notification_area.success("✅ Analysis complete! Download your results below.")
            log_lines.append("\nAnalysis complete!\n")
            log_lines.append("Results saved to places_businesses_without_websites.txt and .csv\n")
            log_html = f'<div id="log-box" class="code-log">' + '<br>'.join(log_lines[-100:]) + '</div>'
            log_area.markdown(log_html, unsafe_allow_html=True)
            with st.expander("⬇️ Download Results"):
                for fname, label in output_files:
                    if os.path.exists(fname):
                        with open(fname, "rb") as f:
                            st.download_button(label=label, data=f, file_name=fname)
        except Exception as e:
            notification_area.error(f"❌ Error: {e}")
        finally:
            builtins.print = orig_print
            progress_bar.empty()

st.markdown(
    '<div class="footer">Made with ❤️ by <a href="https://geethikaisuru.com" class="footer-link" target="_blank">Geethika</a></div>',
    unsafe_allow_html=True
) 