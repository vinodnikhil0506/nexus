import os

from pyfiglet import Figlet, FigletFont
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich import box

console = Console()

# 1. Generate the Figlet logo structure
fig = Figlet(font="3d", width=200)
logo = fig.renderText("N e x u s")
lines = logo.splitlines()

# Color spectrum mapping: Cyan -> Green -> Yellow -> Orange
gradient = [
    (0, 130, 180),   # Dark Cyan
    (0, 240, 255),   # Light Cyan
    (0, 255, 120),   # Green
    (170, 255, 0),   # Yellow-Green
    (255, 255, 0),   # Yellow
    (255, 150, 0),   # Orange
]

max_len = max(len(x) for x in lines) if lines else 1
total_rows = len(lines)

def lerp(a, b, t):
    return int(a + (b - a) * t)

def get_pixel_color(x, y, is_shadow=False):
    p_x = x / max(1, max_len - 1)
    pos = p_x * (len(gradient) - 1)
    i = int(pos)
    j = min(i + 1, len(gradient) - 1)
    t_x = pos - i
    
    base_r = lerp(gradient[i][0], gradient[j][0], t_x)
    base_g = lerp(gradient[i][1], gradient[j][1], t_x)
    base_b = lerp(gradient[i][2], gradient[j][2], t_x)
    
    y_factor = y / max(1, total_rows - 1)
    brightness = 0.75 + (y_factor * 0.45) 
    
    r = int(base_r * brightness)
    g = int(base_g * brightness)
    b = int(base_b * brightness)
    
    if is_shadow:
        r = max(15, r // 4)
        g = max(15, g // 4)
        b = max(15, b // 4)
        
    return max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))

# 2. Build the gradient text object for the logo
logo_text = Text()
#logo_text.append("\n")
for row_idx, line in enumerate(lines):
    for col_idx, ch in enumerate(line):
        if ch == " ":
            logo_text.append(" ")
            continue
        
        if ch in ("░", "▒", "▓"):
            r, g, b = get_pixel_color(col_idx, row_idx, is_shadow=True)
            logo_text.append("█", style=f"rgb({r},{g},{b})")
        else:
            r, g, b = get_pixel_color(col_idx, row_idx, is_shadow=False)
            logo_text.append("█", style=f"bold rgb({r},{g},{b})")
    logo_text.append("\n")
logo_text.append("Connecting engineers with unified agentic AI")

# 3. Create metadata column text
user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
nexus_root = os.environ.get("NEXUS_ROOT") or "unknown"
info_text = Text()
info_text.append("NEXUS ENGINE v1.0.0\n", style="bold white")
info_text.append("Workspace: ", style="bold white")
info_text.append(f"{nexus_root}\n", style="cyan")
info_text.append("GitHub:    ", style="bold white")
info_text.append("github.com/vinodnikhil0506/nexus\n\n", style="cyan")
info_text.append("AI Agent:  ", style="bold white")
info_text.append("Claude\n", style="green")
info_text.append("Domains:   ", style="bold white")
info_text.append("2\n", style="cyan")
info_text.append("MCPs:      ", style="bold white")
info_text.append("4\n", style="cyan")
info_text.append("Skills:    ", style="bold white")
info_text.append("4\n", style="cyan")
info_text.append("IPs:       ", style="bold white")
info_text.append("VeriSight\n\n", style="bold cyan")
info_text.append(f"Welcome {user}!", style="bold green")

# 4. Construct the layout table without printing it on import
# The caller decides when to render it, so there is only one visible splash.
table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
table.add_column("Logo", justify="left", vertical="middle")
table.add_column("Details", justify="left", vertical="middle")
table.add_row(logo_text, info_text)


def show_nexus_logo():
    console.print(table)


if __name__ == "__main__":
    show_nexus_logo()

