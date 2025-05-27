import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import os
from dotenv import load_dotenv
from main_places_api import GooglePlacesBusinessChecker

class BusinessCheckerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("No Site Business Finder - NSBF 🕵️‍♂️")
        self.root.geometry("650x700")
        self.root.configure(bg="#f4f6fb")
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
        style.configure('TLabel', font=('Segoe UI', 11), background="#f4f6fb")
        style.configure('TButton', font=('Segoe UI', 11, 'bold'), padding=6)
        style.configure('TEntry', font=('Segoe UI', 11))
        style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'), foreground='#2d5be3', background="#f4f6fb")

        # Header
        header = ttk.Label(root, text="No Site Business Finder - NSBF", style='Header.TLabel', anchor='center')
        header.pack(pady=(18, 8))

        # Input fields frame
        frm = ttk.Frame(root, padding=18, style='TFrame')
        frm.pack(fill=tk.X, padx=30, pady=(0, 10))

        ttk.Label(frm, text="Location:").grid(row=0, column=0, sticky=tk.W, pady=6)
        self.location_var = tk.StringVar(value="Nugegoda, Sri Lanka")
        loc_entry = ttk.Entry(frm, textvariable=self.location_var, width=38)
        loc_entry.grid(row=0, column=1, padx=8, pady=6)

        ttk.Label(frm, text="Max Results:").grid(row=1, column=0, sticky=tk.W, pady=6)
        self.max_results_var = tk.StringVar(value="50")
        max_entry = ttk.Entry(frm, textvariable=self.max_results_var, width=12)
        max_entry.grid(row=1, column=1, sticky=tk.W, padx=8, pady=6)

        # Gemini API Key status log
        gemini_key = os.environ.get("GEMINI_API_KEY")
        gemini_status = "Found" if gemini_key else "Not Found"
        gemini_color = "#228B22" if gemini_key else "#B22222"
        self.gemini_status_label = tk.Label(frm, text=f"Gemini API Key: {gemini_status}", fg=gemini_color, bg="#f4f6fb", font=('Segoe UI', 9, 'bold'))
        self.gemini_status_label.grid(row=1, column=2, padx=(16, 0), sticky=tk.W)

        ttk.Label(frm, text="Batch Size:").grid(row=2, column=0, sticky=tk.W, pady=6)
        self.batch_size_var = tk.StringVar(value="10")
        batch_entry = ttk.Entry(frm, textvariable=self.batch_size_var, width=12)
        batch_entry.grid(row=2, column=1, sticky=tk.W, padx=8, pady=6)

        # Places API Key status log
        places_key = os.environ.get("GOOGLE_PLACES_API_KEY")
        places_status = "Found" if places_key else "Not Found"
        places_color = "#228B22" if places_key else "#B22222"
        self.places_status_label = tk.Label(frm, text=f"Places API Key: {places_status}", fg=places_color, bg="#f4f6fb", font=('Segoe UI', 9, 'bold'))
        self.places_status_label.grid(row=2, column=2, padx=(16, 0), sticky=tk.W)

        # Add Places API button
        self.places_btn = ttk.Button(frm, text="Analyse with Places API", command=self.start_places_analysis, style='TButton')
        self.places_btn.grid(row=4, column=0, columnspan=2, pady=(8, 0), sticky=tk.EW)

        # Output area frame
        output_frame = ttk.Frame(root, padding=(10, 8, 10, 10), style='TFrame')
        output_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))
        
        self.output = scrolledtext.ScrolledText(
            output_frame, wrap=tk.WORD, height=18, width=80, state='disabled',
            font=('Consolas', 11), bg="#eaf0fa", fg="#222", relief=tk.FLAT, borderwidth=0
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        # Place footer directly below output area, always visible
        footer = tk.Label(
            output_frame,
            text="Made with ❤️ by Geethika",
            fg="#2d5be3",
            bg="#eaf0fa",
            font=('Segoe UI', 10, 'italic', 'underline'),
            cursor="hand2"
        )
        footer.pack(side=tk.BOTTOM, pady=(4, 2))
        def open_author_link(event):
            import webbrowser
            webbrowser.open_new("https://geethikaisuru.com")
        footer.bind("<Button-1>", open_author_link)

    def start_places_analysis(self):
        self.places_btn.config(state=tk.DISABLED)
        self.output.config(state='normal')
        self.output.delete(1.0, tk.END)
        self.output.insert(tk.END, "Starting analysis with Google Places API...\n")
        self.output.config(state='disabled')
        threading.Thread(target=self.run_places_checker, daemon=True).start()

    def run_places_checker(self):
        from dotenv import load_dotenv
        load_dotenv()
        import os
        if not os.environ.get("GEMINI_API_KEY"):
            self.append_output("ERROR: GEMINI_API_KEY is not set in environment or .env file.\n")
            self.places_btn.config(state=tk.NORMAL)
            return
        if not os.environ.get("GOOGLE_PLACES_API_KEY"):
            self.append_output("ERROR: GOOGLE_PLACES_API_KEY is not set in environment or .env file.\n")
            self.places_btn.config(state=tk.NORMAL)
            return
        location = self.location_var.get().strip() or "Nugegoda, Sri Lanka"
        try:
            max_results = int(self.max_results_var.get())
        except ValueError:
            max_results = 50
        try:
            batch_size = int(self.batch_size_var.get())
        except ValueError:
            batch_size = 10
        checker = GooglePlacesBusinessChecker()
        import builtins
        orig_print = print
        def print_to_output(*args, **kwargs):
            msg = ' '.join(str(a) for a in args)
            self.append_output(msg + '\n')
            orig_print(*args, **kwargs)
        builtins.print = print_to_output
        try:
            checker.run_search(location, max_results=max_results, batch_size=batch_size)
            self.append_output("\nAnalysis complete!\n")
            self.append_output(f"Results saved to places_businesses_without_websites.txt and .csv\n")
        except Exception as e:
            self.append_output(f"Error: {e}\n")
        finally:
            builtins.print = orig_print
            self.places_btn.config(state=tk.NORMAL)

    def append_output(self, text):
        self.output.config(state='normal')
        self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = BusinessCheckerGUI(root)
    root.mainloop() 