"""In-memory announcement feed (runtime broadcast to players)."""

ANNOUNCEMENTS = []


def add_announcement(message, timestamp):
    ANNOUNCEMENTS.append({"message": message, "timestamp": timestamp})


def list_announcements():
    return list(ANNOUNCEMENTS)