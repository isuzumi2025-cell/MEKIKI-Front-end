import customtkinter as ctk
from PIL import Image, ImageTk, ImageChops, ImageEnhance
import threading

class MatchSimulatorWindow(ctk.CTkToplevel):
    """
    Visual Match Simulator & LLM Inference Interface
    オニオンスキンによる視覚的比較と、LLMによる構文推論を行うデバッグウィンドウ。
    """
    def __init__(self, parent, web_image: Image.Image, pdf_image: Image.Image, 
                 web_text: str, pdf_text: str, on_llm_request=None, on_save_callback=None):
        super().__init__(parent)
        self.title("🔬 Unified Inspection Editor (Simulator + Edit)")
        self.geometry("1400x950")
        
        self.web_image = web_image
        self.pdf_image = pdf_image
        self.web_text = web_text
        self.pdf_text = pdf_text
        self.on_llm_request = on_llm_request
        self.on_save_callback = on_save_callback
        
        self.opacity = 0.5
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        self._build_ui()
        self._update_preview()
        
    def _build_ui(self):
        # Top: Controls
        ctrl_frame = ctk.CTkFrame(self)
        ctrl_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(ctrl_frame, text="Opacity (Web <-> PDF):").pack(side="left", padx=5)
        self.opacity_slider = ctk.CTkSlider(ctrl_frame, from_=0.0, to=1.0, command=self._on_opacity_change)
        self.opacity_slider.set(0.5)
        self.opacity_slider.pack(side="left", fill="x", expand=True, padx=10)
        
        ctk.CTkLabel(ctrl_frame, text="Scale:").pack(side="left", padx=5)
        self.scale_slider = ctk.CTkSlider(ctrl_frame, from_=0.5, to=2.0, command=self._on_scale_change)
        self.scale_slider.set(1.0)
        self.scale_slider.pack(side="left", fill="x", expand=True, padx=10)

        # Nudge Controls (Alignment)
        ctk.CTkLabel(ctrl_frame, text="X Offset:").pack(side="left", padx=5)
        self.x_slider = ctk.CTkSlider(ctrl_frame, from_=-50, to=50, command=self._on_offset_change)
        self.x_slider.set(0)
        self.x_slider.pack(side="left", width=100)

        ctk.CTkLabel(ctrl_frame, text="Y Offset:").pack(side="left", padx=5)
        self.y_slider = ctk.CTkSlider(ctrl_frame, from_=-50, to=50, command=self._on_offset_change)
        self.y_slider.set(0)
        self.y_slider.pack(side="left", width=100)

        # Confirm Button
        ctk.CTkButton(ctrl_frame, text="💾 Save Sync", fg_color="#4CAF50", command=self._on_save).pack(side="right", padx=10)
        
        # Middle: Visualizations
        viz_frame = ctk.CTkFrame(self)
        viz_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 3 Panels: Web, Onion, PDF
        self.panel_web = ctk.CTkLabel(viz_frame, text="Web Source")
        self.panel_web.pack(side="left", fill="both", expand=True, padx=2)
        
        self.panel_onion = ctk.CTkLabel(viz_frame, text="Onion Skin")
        self.panel_onion.pack(side="left", fill="both", expand=True, padx=2)
        
        self.panel_pdf = ctk.CTkLabel(viz_frame, text="PDF Source")
        self.panel_pdf.pack(side="left", fill="both", expand=True, padx=2)
        
        # Bottom: Text & LLM
        text_frame = ctk.CTkScrollableFrame(self, height=300)
        text_frame.pack(fill="x", padx=10, pady=5)
        
        # Web Text
        w_frame = ctk.CTkFrame(text_frame)
        w_frame.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(w_frame, text="Web Text (OCR)").pack()
        self.web_text_box = ctk.CTkTextbox(w_frame, height=150)
        self.web_text_box.insert("1.0", self.web_text)
        self.web_text_box.pack(fill="both", expand=True)
        
        # PDF Text
        p_frame = ctk.CTkFrame(text_frame)
        p_frame.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(p_frame, text="PDF Text (OCR)").pack()
        self.pdf_text_box = ctk.CTkTextbox(p_frame, height=150)
        self.pdf_text_box.insert("1.0", self.pdf_text)
        self.pdf_text_box.pack(fill="both", expand=True)
        
        # LLM Result
        l_frame = ctk.CTkFrame(text_frame)
        l_frame.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkButton(l_frame, text="🧠 Run LLM Inference", command=self._run_llm).pack(pady=2)
        self.llm_status = ctk.CTkLabel(l_frame, text="Ready") # Typo fix satus -> status
        self.llm_status.pack()
        self.llm_result_box = ctk.CTkTextbox(l_frame, height=120, fg_color="#2D2D2D")
        self.llm_result_box.pack(fill="both", expand=True)

    def _on_offset_change(self, val):
        self.offset_x = int(self.x_slider.get())
        self.offset_y = int(self.y_slider.get())
        self._update_preview()

    def _on_opacity_change(self, val):
        self.opacity = float(val)
        self._update_preview()
        
    def _on_scale_change(self, val):
        self.scale = float(val)
        self._update_preview()
        
    def _update_preview(self):
        # Resize images based on scale
        w, h = self.web_image.size
        new_size = (int(w * self.scale), int(h * self.scale))
        
        w_img = self.web_image.resize(new_size, Image.LANCZOS)
        p_img = self.pdf_image.resize(new_size, Image.LANCZOS)
        
        # Apply offset to PDF text logic? No, just visual shift of PDF image
        # Create a blank canvas for PDF to shift it
        # Actually simplest is to paste p_img onto a new canvas with offset
        
        canvas_w = new_size[0]
        canvas_h = new_size[1]
        
        p_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0,0,0,0))
        # Paste p_img at offset
        p_canvas.paste(p_img, (self.offset_x, self.offset_y))
        
        p_img_shifted = p_canvas
        
        # Create CTkImages
        self.ctk_web = ctk.CTkImage(w_img, size=new_size)
        self.ctk_pdf = ctk.CTkImage(p_img_shifted, size=new_size) # Use shifted for display?
        # Or just use p_img_shifted for Onion Skin and keep PDF panel original?
        # User wants to align them. So ideally both change?
        # Let's show shifted PDF in PDF panel too so user sees what moves.
        self.ctk_pdf = ctk.CTkImage(p_img_shifted, size=new_size)
        
        self.panel_web.configure(image=self.ctk_web, text="")
        self.panel_pdf.configure(image=self.ctk_pdf, text="")
        
        # Onion Skin
        # Make sure modes match
        w_img = w_img.convert("RGBA")
        
        # Blend
        onion = Image.blend(w_img, p_img_shifted, self.opacity)
        self.ctk_onion = ctk.CTkImage(onion, size=new_size)
        self.panel_onion.configure(image=self.ctk_onion, text="")
        
    def _run_llm(self):
        if not self.on_llm_request:
            self.llm_status.configure(text="Callback not set")
            return
            
        self.llm_status.configure(text="Thinking...", text_color="yellow")
        self.llm_result_box.delete("1.0", "end")
        self.update()
        
        def task():
            try:
                # Use current text from boxes (editable!)
                curr_web = self.web_text_box.get("1.0", "end").strip()
                curr_pdf = self.pdf_text_box.get("1.0", "end").strip()
                result = self.on_llm_request(curr_web, curr_pdf)
                self.after(0, lambda: self._show_llm_result(result))
            except Exception as e:
                self.after(0, lambda: self._show_llm_error(str(e)))
                
        threading.Thread(target=task, daemon=True).start()
        
    def _show_llm_result(self, result):
        self.llm_status.configure(text="Done", text_color="green")
        self.llm_result_box.insert("1.0", result)
        
    def _show_llm_error(self, err):
        self.llm_status.configure(text="Error", text_color="red")
        self.llm_result_box.insert("1.0", f"Error: {err}")

    def _on_save(self):
        if self.on_save_callback:
            w_txt = self.web_text_box.get("1.0", "end").strip()
            p_txt = self.pdf_text_box.get("1.0", "end").strip()
            # Also pass offsets?
            # offsets = (self.offset_x, self.offset_y)
            self.on_save_callback(w_txt, p_txt)
            self.destroy()
