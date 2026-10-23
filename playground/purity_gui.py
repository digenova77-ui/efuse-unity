"""Full GUI for the diamond purity playground.

Shows every facet with clarity / color / cut bars,
rise and ceiling status, and actions:
  Refresh, Save report, Apply pressure, Inject impurity.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from diamond_playground import (
    DiamondPlayground, Facet, visual_report, save_report, grade,
)


class PurityApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Diamond Purity Playground")
        self.root.geometry("820x640")
        self.pg = DiamondPlayground()

        # Status bar
        self.status = tk.StringVar(value="ready")
        tk.Label(root, textvariable=self.status, anchor="w",
                 font=("Courier", 10)).pack(fill="x", padx=8, pady=(6, 0))

        # Facet table
        cols = ("name", "kind", "clarity", "color", "cut", "verdict")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (140, 80, 80, 60, 100, 80)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)

        # Report text
        self.text = tk.Text(root, font=("Courier", 10), height=14, wrap="none")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Buttons
        bar = tk.Frame(root)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(bar, text="Refresh", command=self.refresh).pack(side="left", padx=4)
        tk.Button(bar, text="Save report", command=self.on_save).pack(side="left", padx=4)
        tk.Button(bar, text="Apply pressure", command=self.on_pressure).pack(side="left", padx=4)
        tk.Button(bar, text="Inject impurity", command=self.on_impurity).pack(side="left", padx=4)
        tk.Button(bar, text="Reset", command=self.on_reset).pack(side="left", padx=4)

        self.refresh()

    def refresh(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        for f in self.pg.facets:
            if f.kind == "ceiling":
                continue
            g = grade(f)
            self.tree.insert("", "end", values=(
                f.name, f.kind,
                f"{f.clarity} {'✓' if g['clarity']['pass'] else '✗'}",
                f"{f.color} {'✓' if g['color']['pass'] else '✗'}",
                f"{f.cut} {'✓' if g['cut']['pass'] else '✗'}",
                g["verdict"],
            ))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", visual_report(self.pg))
        c = self.pg.ceiling()
        self.status.set(
            f"pressure: {self.pg.pressure_passes}   "
            f"ceiling: {'REACHED' if c.get('reached') else 'NOT REACHED'}"
        )

    def on_save(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All", "*.*")],
            initialfile="purity_report.txt",
        )
        if not path:
            return
        save_report(path, self.pg)
        messagebox.showinfo("Saved", f"Report written to:\n{path}")

    def on_pressure(self) -> None:
        self.pg.apply_pressure()
        self.refresh()

    def on_impurity(self) -> None:
        bad = Facet("tinted_claim", "economy",
                    clarity="FL", color="J", cut="Fair")
        self.pg.facets.insert(-1, bad)  # before ceiling
        self.refresh()

    def on_reset(self) -> None:
        self.pg = DiamondPlayground()
        self.refresh()


def main() -> None:
    root = tk.Tk()
    PurityApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
