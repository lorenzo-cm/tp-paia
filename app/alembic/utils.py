def color(text: str, fg: str = "cyan") -> str:
    colors = {
        "cyan": "\033[96m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "reset": "\033[0m",
        "bold": "\033[1m",
    }
    return f"{colors.get(fg, '')}{text}{colors['reset']}"
