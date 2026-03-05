def get_default_company_logo(index=1):
    """Return a base64-encoded SVG fish icon based on index (1-4)"""
    colors = {
        1: ('#00b4d8', '#0077b6'),  # teal
        2: ('#2ecc71', '#27ae60'),  # green
        3: ('#e67e22', '#d35400'),  # orange
        4: ('#9b59b6', '#8e44ad'),  # purple
    }
    idx = ((index - 1) % 4) + 1
    fill, dark = colors[idx]

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <rect width="100" height="100" rx="16" fill="{fill}"/>
  <!-- body -->
  <ellipse cx="48" cy="50" rx="24" ry="14" fill="white" opacity="0.95"/>
  <!-- tail -->
  <polygon points="24,50 12,38 12,62" fill="white" opacity="0.85"/>
  <!-- eye -->
  <circle cx="62" cy="46" r="3.5" fill="{dark}"/>
  <circle cx="63" cy="45" r="1" fill="white"/>
  <!-- fin -->
  <ellipse cx="50" cy="38" rx="8" ry="4" fill="white" opacity="0.6" transform="rotate(-20,50,38)"/>
  <!-- scales hint -->
  <ellipse cx="46" cy="50" rx="7" ry="5" fill="{fill}" opacity="0.3"/>
  <ellipse cx="55" cy="50" rx="7" ry="5" fill="{fill}" opacity="0.3"/>
</svg>'''

    import base64
    encoded = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{encoded}"