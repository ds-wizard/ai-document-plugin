def progress_percent(completed: int, total: int) -> int:
    if total <= 0:
        return 0
    return round(100 * completed / total)
