"""Render validated ER diagram JSON documents with Graphviz."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
from typing import Any, Mapping

from graphviz import Digraph
from graphviz.backend import ExecutableNotFound

from schema import ERDiagram, SchemaError


class RenderError(RuntimeError):
    """Raised when an ER diagram cannot be rendered."""


def _node_id(prefix: str, *parts: str) -> str:
    """Create a stable Graphviz identifier that cannot clash across node types."""

    safe_parts = [
        "".join(character if character.isalnum() else "_" for character in part)
        for part in parts
    ]
    return "_".join((prefix, *safe_parts))


def _attribute_label(attribute: Any) -> str:
    label = escape(attribute.name)
    if attribute.is_primary_key:
        return f"<<U>{label}</U>>"
    return label


def _add_attribute_nodes(graph: Digraph, entity: Any) -> None:
    entity_id = _node_id("entity", entity.name)
    for attribute in entity.attributes:
        attribute_id = _node_id("attribute", entity.name, attribute.name)
        graph.node(
            attribute_id,
            _attribute_label(attribute),
            shape="ellipse",
            peripheries="2" if attribute.is_multi_valued else "1",
            fontname="Helvetica",
        )
        graph.edge(entity_id, attribute_id, color="#555555")

        if attribute.is_composite:
            for component in attribute.composite:
                component_id = _node_id(
                    "component", entity.name, attribute.name, component
                )
                graph.node(
                    component_id,
                    component,
                    shape="ellipse",
                    fontname="Helvetica",
                )
                graph.edge(attribute_id, component_id, color="#777777")


def _add_relationship_attributes(graph: Digraph, relationship: Any, relationship_id: str) -> None:
    for attribute in relationship.attributes:
        attribute_id = _node_id("relationship_attribute", relationship_id, attribute.name)
        graph.node(
            attribute_id,
            _attribute_label(attribute),
            shape="ellipse",
            peripheries="2" if attribute.is_multi_valued else "1",
            fontname="Helvetica",
        )
        graph.edge(relationship_id, attribute_id, color="#777777")


def _build_graph(diagram: ERDiagram) -> Digraph:
    graph = Digraph("ERDiagram", format="png")
    graph.attr(
        rankdir="LR",
        bgcolor="white",
        fontname="Helvetica",
        nodesep="0.55",
        ranksep="1.0",
        pad="0.25",
        splines="polyline",
    )
    graph.attr("node", color="#333333", fontname="Helvetica", margin="0.12,0.08")
    graph.attr("edge", color="#333333", fontname="Helvetica", fontsize="10")

    for entity in diagram.entities:
        graph.node(
            _node_id("entity", entity.name),
            entity.name,
            shape="box",
            style="rounded,filled",
            fillcolor="#DCEBFA",
            penwidth="1.5",
        )
        _add_attribute_nodes(graph, entity)

    for index, relationship in enumerate(diagram.relationships):
        relationship_id = _node_id(
            "relationship", str(index), relationship.name
        )
        graph.node(
            relationship_id,
            relationship.name,
            shape="diamond",
            style="filled",
            fillcolor="#FFF2CC",
            penwidth="1.5",
            peripheries="2" if relationship.relationship_type == "identifying" else "1",
        )
        if relationship.participants:
            for participant in relationship.participants:
                graph.edge(
                    _node_id("entity", participant.entity),
                    relationship_id,
                    label=participant.cardinality.value,
                )
        else:
            graph.edge(
                _node_id("entity", relationship.entity1),
                relationship_id,
                label=relationship.cardinality.value.split(":")[0],
            )
            graph.edge(
                relationship_id,
                _node_id("entity", relationship.entity2),
                label=relationship.cardinality.value.split(":")[1],
            )
        _add_relationship_attributes(graph, relationship, relationship_id)

    return graph


def _load_diagram(source: str | Path | Mapping[str, Any] | ERDiagram) -> ERDiagram:
    if isinstance(source, ERDiagram):
        return source
    if isinstance(source, Mapping):
        return ERDiagram.from_dict(source)
    return ERDiagram.from_file(source)


def render(
    source: str | Path | Mapping[str, Any] | ERDiagram,
    output: str | Path,
    *,
    format: str | None = None,
) -> Path:
    """Render an ER diagram JSON document and return the generated image path.

    ``source`` may be an input JSON path, a decoded JSON mapping, or an
    already-validated :class:`ERDiagram`. ``output`` is the target image path.
    Supported formats are those installed by Graphviz, including PNG and SVG.
    """

    try:
        diagram = _load_diagram(source)
    except SchemaError as error:
        raise RenderError(f"invalid ER diagram input: {error}") from error

    output_path = Path(output)
    output_format = (format or output_path.suffix.lstrip(".") or "png").lower()
    if not output_format.isidentifier():
        raise RenderError(f"invalid output format: {output_format!r}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filename = output_path.with_suffix("") if output_path.suffix else output_path

    graph = _build_graph(diagram)
    graph.format = output_format
    try:
        generated = Path(
            graph.render(
                filename=str(filename),
                directory=None,
                cleanup=True,
            )
        )
    except ExecutableNotFound as error:
        raise RenderError(
            "Graphviz executable was not found; install Graphviz and ensure "
            "`dot` is available on PATH"
        ) from error
    except Exception as error:
        raise RenderError(f"Graphviz failed to render the diagram: {error}") from error

    return generated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render an ER diagram JSON file using Graphviz."
    )
    parser.add_argument("input", type=Path, help="path to the ER diagram JSON file")
    parser.add_argument(
        "output",
        type=Path,
        help="output image path, for example diagram.png or diagram.svg",
    )
    args = parser.parse_args()

    try:
        generated = render(args.input, args.output)
    except RenderError as error:
        parser.error(str(error))
    print(generated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
