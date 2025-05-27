import streamlit as st
import os
from main_places_api import GooglePlacesBusinessChecker
import time

st.set_page_config(page_title="No Site Business Finder - NSBF", layout="centered")

# --- Sidebar: API Key Management ---
st.sidebar.header("🔑 API Key Management")
with st.sidebar:
    gemini_key = os.environ.get("GEMINI_API_KEY")
    places_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    st.markdown(f'''Gemini API Key: {'✅ <span style="color:#228B22">Found</span>' if gemini_key else '❌ <span style="color:#B22222">Not Found</span>'}''', unsafe_allow_html=True)
    st.markdown(f'''Places API Key: {'✅ <span style="color:#228B22">Found</span>' if places_key else '❌ <span style="color:#B22222">Not Found</span>'}''', unsafe_allow_html=True)
    st.markdown("---")
    new_gemini = st.text_input("Set Gemini API Key (session only)", value="" if gemini_key else "", type="password", key="set_gemini")
    new_places = st.text_input("Set Places API Key (session only)", value="" if places_key else "", type="password", key="set_places")
    if st.button("Set API Keys for Session", use_container_width=True):
        if new_gemini:
            os.environ["GEMINI_API_KEY"] = new_gemini
        if new_places:
            os.environ["GOOGLE_PLACES_API_KEY"] = new_places
        st.success("API keys set for this session!")
        st.experimental_rerun()

# --- Main Area ---
st.markdown("""
<style>
.footer-link { color: #2d5be3; text-decoration: underline; font-style: italic; }
.footer { text-align: center; margin-top: 1.5em; color: #2d5be3; font-size: 1rem; }
.status-green { color: #228B22; font-weight: bold; }
.status-red { color: #B22222; font-weight: bold; }
.code-log {background: #181c20; color: #f4f6fb; border-radius: 8px; padding: 0.7em 1.2em; font-family: 'Fira Mono', monospace; font-size: 1.05em; max-height: 350px; overflow-y: auto; border: 1px solid #222; margin-bottom: 1em;}
@media (max-width: 700px) {
  .code-log { font-size: 0.95em; padding: 0.5em 0.5em; }
}
.st-emotion-cache-1avcm0n { flex-direction: column !important; }
</style>
<script>
window.addEventListener('DOMContentLoaded', function() {
  var logBox = document.getElementById('log-box');
  if (logBox) { logBox.scrollTop = logBox.scrollHeight; }
});
</script>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center; margin-bottom:0.2em;'>No Site Business Finder - NSBF 🕵️‍♂️</h1>", unsafe_allow_html=True)
st.markdown('<div style="text-align:center; font-size:1.2em; color:#2d5be3; margin-bottom:1.5em;">Find Businesses that don\'t have websites in a region.</div>', unsafe_allow_html=True)

with st.container():
    with st.form("input_form"):
        st.markdown("<div style='margin-bottom: 0.5em'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1])
        with col1:
            location = st.text_input("📍 Location", value="Nugegoda, Sri Lanka")
            

        with col2:
            max_results = st.number_input("🔢 Number of Businesses to Analyse", min_value=1, max_value=100, value=50)
            batch_size = st.number_input("📦 Batch Size to Analyse AI", min_value=1, max_value=50, value=10)
            
        st.markdown("<div style='margin-bottom: 0.5em'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("🚀 Analyse with Places API", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("❓ How to use this app / How it works"):
        st.markdown('''
            **How it works:**
            - 🗺️ Searches Google Places for businesses in your chosen location.
            - 🌐 Checks if each business has a website (using Google Places API).
            - 🤖 If not, uses Gemini AI to help decide if the business really has no website.
            - ✅ Only lists businesses as "no website" if both agree.

            **How to use:**
            1. **Set your API keys** (Gemini & Google Places) above if not already set.
            2. **Enter a location** (e.g., city, region, or address).
            3. **Choose the number of businesses** to analyse and the AI batch size.
            4. Click **"Analyse with Places API"** 🚀
            5. Watch the log for progress and download your results when done!

            _Tip: Larger batch sizes may be faster but use more AI quota._
                    ''')


# --- Logging and Progress ---
log_area = st.container()
progress_bar = st.empty()
notification_area = st.empty()

output_files = [
    ("places_businesses_without_websites.txt", "Text Output (.txt)"),
    ("places_businesses_without_websites.csv", "CSV Output (.csv)")
]

# Helper for colored log lines
LOG_LEVELS = {
    'info':   ('ℹ️', '#2d5be3'),
    'success':('✅', '#228B22'),
    'error':  ('❌', '#B22222'),
    'warn':   ('⚠️', '#e6b800'),
    'default':('',   '#f4f6fb'),
}
def format_log_line(line):
    for level, (emoji, color) in LOG_LEVELS.items():
        if line.lower().startswith(level):
            return f'<span style="color:{color}">{emoji} {line}</span>'
    # Highlight certain keywords
    if 'error' in line.lower():
        return f'<span style="color:#B22222">❌ {line}</span>'
    if 'success' in line.lower():
        return f'<span style="color:#228B22">✅ {line}</span>'
    if 'complete' in line.lower():
        return f'<span style="color:#2d5be3">🎉 {line}</span>'
    return f'<span style="color:#f4f6fb">{line}</span>'

if submitted:
    gemini_key = os.environ.get("GEMINI_API_KEY")
    places_key = os.environ.get("GOOGLE_PLACES_API_KEY")
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
            # Format log lines with color and emoji
            formatted = [format_log_line(line) for line in log_lines[-100:]]
            log_html = f'<div id="log-box" class="code-log">' + '<br>'.join(formatted) + '</div>'
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
            log_lines.append("success Analysis complete!")
            log_lines.append("Results saved to places_businesses_without_websites.txt and .csv")
            formatted = [format_log_line(line) for line in log_lines[-100:]]
            log_html = f'<div id="log-box" class="code-log">' + '<br>'.join(formatted) + '</div>'
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

# --- Footer ---
st.markdown(
    '<div class="footer">Made with ❤️ by <a href="https://geethikaisuru.com" class="footer-link" target="_blank">Geethika</a></div>',
    unsafe_allow_html=True
) 