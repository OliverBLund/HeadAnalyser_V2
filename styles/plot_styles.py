"""
HeadAnalyser V2 - Plot format definitions.

These are formatting presets: fonts, ticks, grids, and spines. Data colors live
in styles.plot_palettes.
"""

from .colors import Colors


class PlotStyles:
    """Plot format definitions for different visualization modes.

    The class name is kept for compatibility with existing code. In user-facing
    UI these entries should be called formats, not color styles.
    """

    STYLES = {
        "Default": None,
        "Minimal": None,
        "Scientific": None,
        "Publication": None,
    }

    @classmethod
    def _build_styles(cls):
        return {
            "Default": {
                'font_family': 'sans-serif',
                'font_size': 10,
                'title_size': 13,
                'label_size': 12,
                'tick_size': 10,
                'line_width': 1.0,
                'grid_alpha': 1.0,
                'grid_linestyle': ':',
                'grid_linewidth': 0.65,
                'grid_color': Colors.PLOT_GRID,
                'background': Colors.PLOT_FACE,
                'text_color': Colors.PLOT_TEXT,
                'spine_color': Colors.PLOT_SPINE,
            },
            "Minimal": {
                'font_family': 'sans-serif',
                'font_size': 9,
                'title_size': 12,
                'label_size': 11,
                'tick_size': 9,
                'line_width': 0.8,
                'grid_alpha': 1.0,
                'grid_linestyle': ':',
                'grid_linewidth': 0.5,
                'grid_color': Colors.PLOT_GRID_MINOR,
                'background': Colors.PLOT_FACE,
                'text_color': Colors.PLOT_TEXT,
                'spine_color': Colors.PLOT_SPINE,
            },
            "Scientific": {
                'font_family': 'serif',
                'font_size': 12,
                'title_size': 16,
                'label_size': 14,
                'tick_size': 11,
                'line_width': 1.5,
                'grid_alpha': 0.5,  # Strong grid for scientific
                'grid_linestyle': '-',
                'grid_linewidth': 0.8,
                'grid_color': Colors.PLOT_GRID,
                'background': Colors.PLOT_FACE,
                'text_color': Colors.PLOT_TEXT,
                'spine_color': Colors.TEXT_PRIMARY,
            },
            "Publication": {
                # Clean, professional style inspired by high-quality publication figures
                'font_family': 'sans-serif',
                'font_size': 11,
                'title_size': 14,
                'label_size': 12,
                'tick_size': 10,
                'line_width': 1.2,
                'grid_alpha': 0.4,
                'grid_linestyle': '--',
                'grid_linewidth': 0.6,
                'grid_axis': 'y',  # Only horizontal grid lines
                'grid_color': Colors.PLOT_GRID,
                'background': Colors.PLOT_FACE,
                'text_color': Colors.PLOT_TEXT,
                'spine_color': Colors.PLOT_AXIS,
                'spine_width': 1.5,
                'tick_direction': 'out',
                'tick_length': 5,
                'title_weight': 'bold',
                'label_weight': 'bold',
                'hide_spines': ['top', 'right'],  # Hide top and right spines
            },
        }

    @classmethod
    def get_style(cls, style_name):
        """Get format dictionary by name."""
        styles = cls._build_styles()
        return styles.get(style_name, styles["Default"])

    @classmethod
    def format_names(cls):
        """Return available plot format keys in display order."""
        return tuple(cls.STYLES.keys())

    @classmethod
    def apply_to_axes(cls, ax, style_name):
        """Apply style to matplotlib axes.

        Args:
            ax: Matplotlib axes object
            style_name: Name of style to apply (Default, Minimal, Scientific, Publication)
        """
        style = cls.get_style(style_name)

        # Set background color
        ax.set_facecolor(style['background'])

        # Get tick direction and length (with defaults for backwards compatibility)
        tick_direction = style.get('tick_direction', 'in')
        tick_length = style.get('tick_length', 4)

        # Apply tick parameters
        ax.tick_params(
            labelsize=style['tick_size'],
            colors=style['text_color'],
            width=style['line_width'],
            length=tick_length,
            direction=tick_direction,
        )

        # Get font weight settings (with defaults)
        label_weight = style.get('label_weight', 'normal')
        title_weight = style.get('title_weight', 'normal')

        # Style axis labels
        if ax.xaxis.label:
            ax.xaxis.label.set_size(style['label_size'])
            ax.xaxis.label.set_color(style['text_color'])
            ax.xaxis.label.set_family(style['font_family'])
            ax.xaxis.label.set_weight(label_weight)

        if ax.yaxis.label:
            ax.yaxis.label.set_size(style['label_size'])
            ax.yaxis.label.set_color(style['text_color'])
            ax.yaxis.label.set_family(style['font_family'])
            ax.yaxis.label.set_weight(label_weight)

        # Style title if it exists
        if ax.get_title():
            ax.title.set_size(style['title_size'])
            ax.title.set_color(style['text_color'])
            ax.title.set_family(style['font_family'])
            ax.title.set_weight(title_weight)

        # Style spines (axes borders)
        spine_width = style.get('spine_width', style['line_width'])
        hide_spines = style.get('hide_spines', [])
        for spine_name, spine in ax.spines.items():
            if spine_name in hide_spines:
                spine.set_visible(False)
            else:
                spine.set_visible(True)   # restore if a previous style hid it
                spine.set_linewidth(spine_width)
                spine.set_color(style['spine_color'])

        # Style tick labels
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontfamily(style['font_family'])
            label.set_fontsize(style['tick_size'])
            label.set_color(style['text_color'])

    @classmethod
    def get_grid_props(cls, style_name):
        """Get grid properties for a style.

        Returns:
            dict: Grid properties (alpha, linestyle, linewidth, axis)
        """
        style = cls.get_style(style_name)
        return {
            'alpha': style['grid_alpha'],
            'linestyle': style['grid_linestyle'],
            'linewidth': style['grid_linewidth'],
            'color': style.get('grid_color', Colors.PLOT_GRID),
            'axis': style.get('grid_axis', 'both'),  # 'both', 'x', or 'y'
        }

    @classmethod
    def get_figure_color(cls, style_name):
        """Get figure background color for a style.

        Returns:
            str: Color hex code
        """
        style = cls.get_style(style_name)
        return style['background']

    @classmethod
    def get_text_color(cls, style_name):
        """Get text color for a style.

        Returns:
            str: Color hex code
        """
        style = cls.get_style(style_name)
        return style['text_color']


# ── Popup / tooltip styles ─────────────────────────────────────────────

class PopupStyles:
    """Styles for matplotlib annotation popups (hover tooltips, pinned labels)."""

    STYLES = {
        "Clean": None,
        "Dark": None,
        "Accent": None,
        "Compact": None,
    }

    @classmethod
    def _build_styles(cls):
        return {
            "Clean": {
                'fc': Colors.PLOT_FACE,
                'ec': Colors.PLOT_BORDER,
                'alpha': 0.97,
                'boxstyle': 'round,pad=0.45',
                'text_color': Colors.PLOT_TEXT,
                'fontsize': 9,
            },
            "Dark": {
                'fc': Colors.PLOT_DARK_FACE,
                'ec': Colors.PLOT_DARK_BORDER,
                'alpha': 0.95,
                'boxstyle': 'round,pad=0.45',
                'text_color': Colors.PLOT_DARK_TEXT,
                'fontsize': 9,
            },
            "Accent": {
                'fc': Colors.PLOT_FACE,
                'ec': Colors.ACCENT_PRIMARY,
                'alpha': 0.97,
                'boxstyle': 'round,pad=0.45',
                'text_color': Colors.PLOT_TEXT,
                'fontsize': 9,
            },
            "Compact": {
                'fc': Colors.PLOT_COLORBAR_BG,
                'ec': Colors.PLOT_BORDER,
                'alpha': 0.92,
                'boxstyle': 'round,pad=0.28',
                'text_color': Colors.PLOT_AXIS,
                'fontsize': 8,
            },
        }

    @classmethod
    def get_style(cls, style_name):
        """Get popup style dict by name."""
        styles = cls._build_styles()
        return styles.get(style_name, styles["Clean"])

    @classmethod
    def get_bbox(cls, style_name):
        """Get matplotlib bbox kwargs for the given popup style."""
        s = cls.get_style(style_name)
        return dict(
            boxstyle=s['boxstyle'],
            fc=s['fc'],
            ec=s['ec'],
            alpha=s['alpha'],
        )

    @classmethod
    def get_text_color(cls, style_name):
        """Get text color for the given popup style."""
        return cls.get_style(style_name)['text_color']

    @classmethod
    def get_fontsize(cls, style_name):
        """Get font size for the given popup style."""
        return cls.get_style(style_name)['fontsize']
