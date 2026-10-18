"""Small desktop client for generating and rendering ER diagrams with Gemini."""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from render import RenderError, render
from schema import ERDiagram, SchemaError


PROMPT = """You convert a natural-language database system description into an ER diagram JSON object.

Return ONLY valid JSON. Do not use Markdown code fences, explanations, or additional keys.
The JSON must have exactly this shape:
{
  "entities": [
    {
      "name": "EntityName",
      "attributes": [
        {"name": "AttributeName", "isPrimaryKey": true},
        {"name": "AttributeName", "isMultiValued": true},
        {"name": "AttributeName", "composite": ["ComponentA", "ComponentB"]}
      ]
    }
  ],
  "relationships": [
    {
      "entity1": "EntityName",
      "entity2": "EntityName",
      "name": "RelationshipName",
      "cardinality": "1:1",
      "attributes": [
        {"name": "RelationshipAttribute"}
      ]
    },
    {
      "name": "TernaryRelationshipName",
      "participants": [
        {"entity": "EntityName", "cardinality": "N"},
        {"entity": "AnotherEntity", "cardinality": "N"},
        {"entity": "ThirdEntity", "cardinality": "N"}
      ],
      "attributes": [
        {"name": "RelationshipAttribute"}
      ]
    }
  ]
}

Rules:
- Include every important entity, attribute, and relationship from the description.
- In a binary relationship, "entity1" and "entity2" must be names of entities
  listed in the "entities" array. "name" is the relationship name and must
  never be used as an entity1 or entity2 value. For example, a relationship
  named "Borrows" between Member and Copy must be:
  {"entity1": "Member", "entity2": "Copy", "name": "Borrows", "cardinality": "M:N"}.
- Mark identifier attributes with "isPrimaryKey": true.
- Use "isMultiValued": true for attributes that can have multiple values.
- Use "composite" for attributes made up of smaller attributes.
- Add relationship attributes when a fact belongs to the association rather than
  to either participating entity, such as EnrollmentDate or Grade on an
  enrollment relationship.
- Use "participants" with at least three entity/cardinality objects for ternary
  or higher-order relationships instead of splitting them into binary
  relationships.
- Use only these cardinalities: "1:1", "1:N", "N:1", or "N:M".
- Use participant cardinalities "1" or "N" for ternary relationships.
- Use empty arrays when no entities or relationships are found.

System description:
"""


def load_dotenv(path: str | Path | None = None) -> None:
    """Load simple KEY=VALUE pairs without requiring an extra dependency."""

    dotenv_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().with_name(".env")
    )
    if not dotenv_path.is_file():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        normalized_key = key.strip()
        if value and not os.environ.get(normalized_key, "").strip():
            os.environ[normalized_key] = value


def _extract_json(response: dict[str, Any]) -> dict[str, Any]:
    try:
        parts = response["candidates"][0]["content"]["parts"]
        text = "".join(part["text"] for part in parts if "text" in part).strip()
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Google AI returned no usable text content") from error

    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Google AI returned invalid JSON: {error.msg}") from error
    if not isinstance(parsed, dict):
        raise RuntimeError("Google AI returned JSON that is not an object")
    return parsed


def generate_diagram_json(description: str) -> ERDiagram:
    """Ask Google AI for ER JSON and validate it against the project schema."""

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to a local .env file."
        )
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": PROMPT + description.strip()}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google AI request failed ({error.code}): {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach Google AI: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError("Google AI returned a non-JSON API response") from error

    try:
        return ERDiagram.from_dict(_extract_json(body))
    except SchemaError as error:
        raise RuntimeError(f"Google AI returned invalid ER schema: {error}") from error


class DiagramApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AI-Powered ER Diagram Generator")
        self.root.geometry("680x460")
        self.root.minsize(520, 360)

        tk.Label(
            root,
            text="Describe the system you want to model:",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(12, 4))
        self.prompt_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=15)
        self.prompt_box.pack(fill="both", expand=True, padx=12, pady=4)
        self.prompt_box.insert(
            "1.0",
            "A university has students and courses. Students enroll in courses, "
            "and each course has a code and title.",
        )
        self.generate_button = tk.Button(
            root,
            text="Generate ER Diagram",
            command=self.start_generation,
        )
        self.generate_button.pack(pady=8)
        self.status = tk.Label(root, text="Ready", anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 10))

    def start_generation(self) -> None:
        description = self.prompt_box.get("1.0", tk.END).strip()
        if not description:
            messagebox.showwarning("Missing description", "Enter a system description.")
            return
        self.generate_button.config(state=tk.DISABLED)
        self.status.config(text="Asking Google AI and rendering the diagram...")
        threading.Thread(
            target=self._generate,
            args=(description,),
            daemon=True,
        ).start()

    def _generate(self, description: str) -> None:
        try:
            diagram = generate_diagram_json(description)
            diagram.to_file("generated.json")
            png_path = render(diagram, "generated.png")
            svg_path = render(diagram, "generated.svg")
        except (RenderError, RuntimeError, OSError) as error:
            self.root.after(0, self._show_error, str(error))
            return
        self.root.after(0, self._show_success, png_path, svg_path)

    def _show_error(self, message: str) -> None:
        self.generate_button.config(state=tk.NORMAL)
        self.status.config(text="Generation failed")
        messagebox.showerror("Generation failed", message)

    def _show_success(self, png_path: Path, svg_path: Path) -> None:
        self.generate_button.config(state=tk.NORMAL)
        self.status.config(text=f"Created {png_path} and {svg_path}")
        messagebox.showinfo(
            "Diagram generated",
            f"Saved:\n{png_path}\n{svg_path}\n\ngenerated.json",
        )


def main() -> None:
    load_dotenv()
    root = tk.Tk()
    DiagramApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
