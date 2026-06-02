from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from textwrap import wrap
from uuid import uuid4

from django.conf import settings

from factwise.storage import JSONStorage
from project_board_base import ProjectBoardBase


class ProjectBoardImpl(ProjectBoardBase):
    def __init__(self) -> None:
        """Initialize JSON storage for board persistence; raises no exceptions."""
        self._storage = JSONStorage()

    def _load_boards(self) -> dict[str, dict]:
        """Load stored boards from boards.json; raises ValueError if storage data is invalid."""
        return self._storage.load('boards')

    def _save_boards(self, boards: dict[str, dict]) -> None:
        """Persist boards to boards.json; raises ValueError if the data cannot be serialized."""
        self._storage.save('boards', boards)

    def _load_teams(self) -> dict[str, dict]:
        """Load stored teams from teams.json; raises ValueError if storage data is invalid."""
        return self._storage.load('teams')

    def _load_users(self) -> dict[str, dict]:
        """Load stored users from users.json; raises ValueError if storage data is invalid."""
        return self._storage.load('users')

    def _parse_request(self, request: str) -> dict:
        """Parse a JSON request body; raises ValueError if the input is not valid JSON or an object."""
        if isinstance(request, dict):
            return request
        if isinstance(request, bytes):
            request = request.decode('utf-8')
        if not isinstance(request, str):
            raise ValueError('Invalid JSON request')
        try:
            payload = json.loads(request)
        except json.JSONDecodeError as exc:
            raise ValueError('Invalid JSON request') from exc

        # Some clients accidentally send JSON as a quoted string; parse once more in that case.
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError('Invalid JSON request') from exc

        if not isinstance(payload, dict):
            raise ValueError('Request must be a JSON object')
        return payload

    def _validate_name(self, value: object) -> str:
        """Validate a board or task title; raises ValueError if the value is missing or too long."""
        if not isinstance(value, str) or not value:
            raise ValueError('Name is required')
        if len(value) > 64:
            raise ValueError('Name can be at most 64 characters')
        return value

    def _validate_description(self, value: object) -> str:
        """Validate a description; raises ValueError if the value is invalid or too long."""
        if not isinstance(value, str):
            raise ValueError('Description is required')
        if len(value) > 128:
            raise ValueError('Description can be at most 128 characters')
        return value

    def _validate_status(self, value: object) -> str:
        """Validate a task status; raises ValueError if the status is invalid."""
        if not isinstance(value, str):
            raise ValueError('Status is required')
        if value not in {'OPEN', 'IN_PROGRESS', 'COMPLETE'}:
            raise ValueError('Invalid task status')
        return value

    def _ensure_team_exists(self, team_id: object) -> str:
        """Validate that a team exists; raises ValueError if the team id is invalid or missing."""
        if not isinstance(team_id, str) or not team_id:
            raise ValueError('Team id is required')
        teams = self._load_teams()
        if team_id not in teams:
            raise ValueError('Team not found')
        return team_id

    def _ensure_user_exists(self, user_id: object) -> str:
        """Validate that a user exists; raises ValueError if the user id is invalid or missing."""
        if not isinstance(user_id, str) or not user_id:
            raise ValueError('User id is required')
        users = self._load_users()
        if user_id not in users:
            raise ValueError('User not found')
        return user_id

    def _find_task(self, task_id: str) -> tuple[dict[str, dict], dict | None, str | None]:
        """Find a task across all boards; raises no exceptions and returns the boards, board, and task ids."""
        boards = self._load_boards()
        # scan every board because tasks are stored nested under boards
        for board_id, board in boards.items():
            task = board.get('tasks', {}).get(task_id)
            if task is not None:
                # return the full boards mapping, the board containing the task, and the board id
                return boards, board, board_id
        return boards, None, None

    def create_board(self, request: str) -> str:
        """Create a board and return its id; raises ValueError for invalid input, duplicates, or missing team."""
        payload = self._parse_request(request)
        name = self._validate_name(payload.get('name'))
        description = self._validate_description(payload.get('description'))
        team_id = self._ensure_team_exists(payload.get('team_id'))
        creation_time = payload.get('creation_time')
        if not isinstance(creation_time, str) or not creation_time:
            raise ValueError('Creation time is required')

        boards = self._load_boards()
        if any(board.get('team_id') == team_id and board.get('name') == name for board in boards.values()):
            raise ValueError('Board name must be unique for the team')

        board_id = str(uuid4())
        boards[board_id] = {
            'id': board_id,
            'name': name,
            'description': description,
            'team_id': team_id,
            # boards start in OPEN state so tasks may be added
            'status': 'OPEN',
            'creation_time': creation_time,
            'end_time': None,
            'tasks': {},
        }
        self._save_boards(boards)
        return json.dumps({'id': board_id})

    def close_board(self, request: str) -> str:
        """Close a board and return its id; raises ValueError if the board is missing, closed, or incomplete."""
        payload = self._parse_request(request)
        board_id = payload.get('id')
        if not isinstance(board_id, str) or not board_id:
            raise ValueError('Board id is required')

        boards = self._load_boards()
        board = boards.get(board_id)
        if board is None:
            raise ValueError('Board not found')
        if board.get('status') == 'CLOSED':
            raise ValueError('Board is already closed')

        tasks = board.get('tasks', {})
        # ensure all tasks are COMPLETE before allowing a board to be closed
        if any(task.get('status') != 'COMPLETE' for task in tasks.values()):
            raise ValueError('All tasks must be COMPLETE before closing the board')

        board['status'] = 'CLOSED'
        board['end_time'] = datetime.now(timezone.utc).isoformat()
        self._save_boards(boards)
        return json.dumps({'id': board_id})

    def add_task(self, request: str) -> str:
        """Add a task to a board and return its id; raises ValueError if the board, user, or input is invalid."""
        payload = self._parse_request(request)
        board_id = payload.get('board_id')
        title = self._validate_name(payload.get('title'))
        description = self._validate_description(payload.get('description'))
        user_id = self._ensure_user_exists(payload.get('user_id'))
        creation_time = payload.get('creation_time')
        if not isinstance(creation_time, str) or not creation_time:
            raise ValueError('Creation time is required')

        boards = self._load_boards()
        board = boards.get(board_id) if isinstance(board_id, str) else None
        if board is None:
            raise ValueError('Board not found')
        # only allow tasks to be added while the board is OPEN
        if board.get('status') != 'OPEN':
            raise ValueError('Tasks can only be added to an OPEN board')

        tasks = board.setdefault('tasks', {})
        if any(task.get('title') == title for task in tasks.values()):
            raise ValueError('Task title must be unique within the board')

        task_id = str(uuid4())
        tasks[task_id] = {
            'id': task_id,
            'title': title,
            'description': description,
            'user_id': user_id,
            'status': 'OPEN',
            'creation_time': creation_time,
        }
        self._save_boards(boards)
        return json.dumps({'id': task_id})

    def update_task_status(self, request: str):
        """Update a task status and return its id; raises ValueError if the request, task, or status is invalid."""
        payload = self._parse_request(request)
        task_id = payload.get('id')
        status = self._validate_status(payload.get('status'))
        if not isinstance(task_id, str) or not task_id:
            raise ValueError('Task id is required')

        # find the task by scanning boards and update its status in-place
        boards = self._load_boards()
        for board in boards.values():
            tasks = board.get('tasks', {})
            task = tasks.get(task_id)
            if task is not None:
                task['status'] = status
                self._save_boards(boards)
                return json.dumps({'id': task_id})

        raise ValueError('Task not found')

    def list_boards(self, request: str) -> str:
        """List open boards for a team; raises ValueError if the request is invalid or the team is missing."""
        payload = self._parse_request(request)
        team_id = self._ensure_team_exists(payload.get('id'))

        boards = self._load_boards()
        response = [
            {'id': board_id, 'name': board.get('name')}
            for board_id, board in boards.items()
            if board.get('team_id') == team_id and board.get('status') == 'OPEN'
        ]
        return json.dumps(response)

    def export_board(self, request: str) -> str:
        """Export a board to a formatted text file; raises ValueError if the board is missing or the file cannot be written."""
        payload = self._parse_request(request)
        board_id = payload.get('id')
        if not isinstance(board_id, str) or not board_id:
            raise ValueError('Board id is required')

        boards = self._load_boards()
        board = boards.get(board_id)
        if board is None:
            raise ValueError('Board not found')

        users = self._load_users()
        tasks = board.get('tasks', {})
        status_counts = {'OPEN': 0, 'IN_PROGRESS': 0, 'COMPLETE': 0}
        for task in tasks.values():
            task_status = task.get('status', 'OPEN')
            if task_status in status_counts:
                status_counts[task_status] += 1

        # write exports to the project's out directory; keep files readable text reports
        out_dir = Path(settings.BASE_DIR) / 'out'
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f'board_{board_id}.txt'
        file_path = out_dir / filename

        # helpers below build a simple ASCII box-style report for readability
        def border(width: int) -> str:
            return f'┌{"─" * (width - 2)}┐\n'

        def line(text: str, width: int) -> str:
            # left-align text and truncate to fit the box width
            cleaned = text[: width - 4]
            return f'│ {cleaned.ljust(width - 4)} │\n'

        def section_header(text: str, width: int) -> str:
            # draw a centered section header inside the box
            banner = f' {text} '
            banner = banner.center(width - 2, '─')
            return f'├{banner}┤\n'

        def wrap_field(label: str, value: str, width: int) -> list[str]:
            wrapped = wrap(value or '-', width=width - len(label) - 4) or ['-']
            return [f'{label}{wrapped[0]}'] + [f"{' ' * len(label)}{chunk}" for chunk in wrapped[1:]]

        task_icon = {'OPEN': '[ ]', 'IN_PROGRESS': '[~]', 'COMPLETE': '[✓]'}
        task_sections: list[str] = []
        for status in ('OPEN', 'IN_PROGRESS', 'COMPLETE'):
            task_sections.append(f'[{status}] {status_counts[status]}')

        width = 96
        lines: list[str] = []
        lines.append(border(width))
        lines.append(line(f'BOARD REPORT: {board.get("name", "-")}', width))
        lines.append(line(f'Description : {board.get("description", "-")}', width))
        lines.append(line(f'Status      : {board.get("status", "-")}', width))
        lines.append(line(f'Team        : {board.get("team_id", "-")}', width))
        lines.append(line(f'Created     : {board.get("creation_time", "-")}', width))
        lines.append(line(f'Closed      : {board.get("end_time") or "-"}', width))
        lines.append(line(f'Summary     : {' | '.join(task_sections)}', width))
        lines.append(section_header(' TASKS ', width))

        for status in ('OPEN', 'IN_PROGRESS', 'COMPLETE'):
            lines.append(line(f'{task_icon[status]} {status}', width))
            matching_tasks = [task for task in tasks.values() if task.get('status') == status]
            if not matching_tasks:
                lines.append(line('  (none)', width))
            for task in matching_tasks:
                assigned_user = users.get(task.get('user_id'), {})
                assignee = assigned_user.get('display_name') or assigned_user.get('name') or task.get('user_id', '-')
                task_lines = [
                    f'Title      : {task.get("title", "-")}',
                    f'Description: {task.get("description", "-")}',
                    f'Assigned   : {assignee} ({task.get("user_id", "-")})',
                    f'Created    : {task.get("creation_time", "-")}',
                ]
                for task_line in task_lines:
                    for chunk in wrap(task_line, width=width - 4) or ['-']:
                        lines.append(line(f'  {chunk}', width))
                lines.append(line('  ' + '─' * (width - 6), width))

        lines.append(f'└{"─" * (width - 2)}┘\n')
        with file_path.open('w', encoding='utf-8') as handle:
            handle.writelines(lines)
        return json.dumps({'out_file': filename})