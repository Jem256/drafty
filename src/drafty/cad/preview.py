"""Render a DXF to an SVG preview using the ezdxf drawing add-on (matplotlib backend)."""

from __future__ import annotations

from pathlib import Path

import ezdxf


def render_svg(dxf_path: str | Path, svg_path: str | Path) -> Path:
    """Render the modelspace of a DXF to an SVG file and return the path."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    dxf_path = Path(dxf_path)
    svg_path = Path(svg_path)
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    doc = ezdxf.readfile(dxf_path)
    figure = plt.figure()
    axes = figure.add_axes([0, 0, 1, 1])
    axes.set_axis_off()
    backend = MatplotlibBackend(axes)
    Frontend(RenderContext(doc), backend).draw_layout(doc.modelspace(), finalize=True)
    figure.savefig(svg_path, format="svg")
    plt.close(figure)
    return svg_path
