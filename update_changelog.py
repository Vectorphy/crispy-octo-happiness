import re

def patch():
    with open('CHANGELOG.md', 'r') as f:
        content = f.read()

    new_release = """## [1.0.0-rc.3] - 2026-09-29

### Added
- **Alphanumeric Task IDs**: `Task ID`s are now 4-character alphanumeric strings, avoiding confusion across different groups where multiple tasks had the same sequential ID.
- **Task Pagination**: Tasks are now listed with pagination (15 tasks per page) using interactive Discord UI buttons, mitigating Discord's Embed character and field limitations that caused 400 Bad Request HTTP errors.

### Changed
- **Optional Mentions and Names**:
  - `mentions` is now optional for the `/checkin` command.
  - `name` is now optional for the `/create_group` command. If omitted, a UUID-based name is generated automatically.

### Fixed
- Fixed HTTP 400 Bad Request error caused by embeds exceeding Discord's limits during `list_tasks`.
- Fixed CI formatting checks by correctly enforcing `ruff format` and `ruff check`.
- Scoped Task Commands so users can no longer manipulate tasks outside groups they belong to.
- Dropped out pomodoro users can now successfully rejoin an ongoing session via `/resume_pomodoro` and have their absent count reset.
- Refactored `Join Group` invitations to use `discord.ui.View` with persistent Accept/Decline buttons rather than a timeout-prone `wait_for` logic.

"""

    content = content.replace('## [1.0.0-rc.3] - 2026-09-29\n\n', new_release)

    with open('CHANGELOG.md', 'w') as f:
        f.write(content)

patch()
