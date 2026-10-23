"""Simple GUI for the diamond purity report.

Buttons:
  Refresh  — redraw the report
  Save     — write the report to a chosen file
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from diamond_playground import DiamondPlayground, visual_report, save_report


def main() -> None:
    root = tk.Tk()
    root.title("Diamond Purity Report")
    root.geometry("640x480")

    playground = DiamondPlayground()

    text = tk.Text(root, font=("Courier", 11), wrap="none")
    text.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh() -> None:
        text.delete("1.0", "end")
        text.insert("1.0", visual_report(playground))

    def on_save() -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
            initialfile="purity_report.txt",
        )
        if not path:
            return
        save_report(path, playground)
        messagebox.showinfo("Saved", f"Report written to:\n{path}")

    bar = tk.Frame(root)
    bar.pack(fill="x", padx=8, pady=(0, 8))
    tk.Button(bar, text="Refresh", command=refresh).pack(side="left", padx=4)
    tk.Button(bar, text="Save report", command=on_save).pack(side="left", padx=4)

    refresh()
    root.mainloop()


if __name__ == "__main__":
    main()
