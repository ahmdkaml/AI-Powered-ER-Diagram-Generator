# AI-Powered ER Diagram Generator

## Lab Description

This lab implements an end-to-end **natural-language-to-ER-diagram** pipeline for the Database Systems course.

The application:

1. Accepts a plain-text description of a database system.
2. Sends the description to Google Gemini with a prompt requiring a structured ER JSON document.
3. Validates the returned JSON against the project schema.
4. Saves the validated model as `generated.json`.
5. Uses Graphviz to render the model as `generated.png` and `generated.svg`.

The project also supports rendering an existing JSON file directly, without calling Google Gemini.

## Work Completed

### `schema.py`

Defines the validated ER diagram data model:

- `ERDiagram`
- `Entity`
- `Attribute`
- `Relationship`
- `Cardinality`

Supported attribute types include:

- Simple attributes
- Primary-key attributes
- Multivalued attributes
- Composite attributes

The schema validates duplicate names, invalid field types, unsupported cardinalities, malformed JSON, and relationships that reference unknown entities.

### `render.py`

Implements the Graphviz rendering engine.

ER elements are represented as follows:

| ER element | Diagram representation |
|---|---|
| Entity | Rounded rectangle |
| Relationship | Diamond |
| Attribute | Ellipse |
| Primary key | Underlined attribute |
| Multivalued attribute | Double ellipse |
| Composite attribute | Parent attribute connected to component attributes |
| Cardinality | Labels on relationship edges |

The renderer supports PNG, SVG, and other formats supported by Graphviz.

### `main.py`

Provides a small Tkinter desktop application that:

- Accepts a natural-language system description.
- Loads `GEMINI_API_KEY` from `.env`.
- Sends a JSON-only generation prompt to Google Gemini.
- Parses and validates Gemini's response.
- Saves the generated JSON.
- Produces PNG and SVG ER diagrams.
- Displays clear success and error messages.

### `test.json`

Contains a sample ER diagram with:

- Employee and Department entities
- Primary-key attributes
- A composite attribute
- Multivalued attributes
- An `N:1` relationship

## Requirements

- Python 3.10 or newer
- Graphviz installed and available as `dot` on `PATH`
- A Google AI Studio API key for the Gemini integration

The Python Graphviz package can be installed with:

```powershell
python -m pip install graphviz
```

On Windows, install Graphviz separately and confirm that this command works:

```powershell
dot -V
```

## Configuration

Create a file named `.env` in the project directory:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-3.1-flash-lite
```

Do not commit `.env` or expose the API key. The repository ignores the key file and generated output files.

## How to Use

### Generate a Diagram from a Text Description

Start the graphical application:

```powershell
python main.py
```

Enter a description such as:

```text
A school database manages students, teachers, courses, classes,
enrollments, and grades. Students can enroll in multiple classes,
and each class can have multiple students.
```

Click **Generate ER Diagram**. The application creates:

- `generated.json` - validated ER diagram data
- `generated.png` - rendered PNG diagram
- `generated.svg` - rendered SVG diagram

### Render an Existing JSON File

Render the included sample:

```powershell
python render.py test.json diagram.png
```

To produce SVG instead:

```powershell
python render.py test.json diagram.svg
```

The renderer can also be used from Python:

```python
from render import render

output_path = render("test.json", "diagram.png")
print(output_path)
```

## JSON Structure

The renderer expects this general structure:

```json
{
  "entities": [
    {
      "name": "Student",
      "attributes": [
        {
          "name": "StudentID",
          "isPrimaryKey": true
        },
        {
          "name": "Name",
          "composite": ["FirstName", "LastName"]
        },
        {
          "name": "Phone",
          "isMultiValued": true
        }
      ]
    }
  ],
  "relationships": [
    {
      "entity1": "Student",
      "entity2": "Class",
      "name": "enrolls_in",
      "cardinality": "N:M"
    }
  ]
}
```

Supported cardinalities are:

```text
1:1
1:N
N:1
N:M
```

## Generated Files

Generated diagrams and AI output are intentionally kept locally for inspection and are excluded from version control:

- `generated.json`
- `generated.png`
- `generated.svg`
- `.env`

