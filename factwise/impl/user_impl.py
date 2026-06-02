from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from factwise.storage import JSONStorage
from user_base import UserBase


class UserImpl(UserBase):
    def __init__(self) -> None:
        """Initialize JSON storage for user persistence; raises no exceptions."""
        self._storage = JSONStorage()

    def _load_users(self) -> dict[str, dict]:
        """Load stored users from users.json; raises ValueError if storage data is invalid."""
        return self._storage.load('users')

    def _save_users(self, users: dict[str, dict]) -> None:
        """Persist users to users.json; raises ValueError if the data cannot be serialized."""
        self._storage.save('users', users)

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

    def create_user(self, request: str) -> str:
        """Create a user, enforcing uniqueness and length constraints; raises ValueError for invalid input."""
        payload = self._parse_request(request)
        name = payload.get('name')
        display_name = payload.get('display_name')

        if not isinstance(name, str) or not name:
            # name must be a non-empty string (used as a stable unique handle)
            raise ValueError('User name is required')
        if len(name) > 64:
            # prevent excessively long usernames for storage/readability
            raise ValueError('User name can be at most 64 characters')
        if not isinstance(display_name, str):
            # display_name is shown in UI; must be a string
            raise ValueError('Display name is required')
        if len(display_name) > 64:
            # keep display names reasonably short
            raise ValueError('Display name can be at most 64 characters')

        users = self._load_users()
        if any(user.get('name') == name for user in users.values()):
            raise ValueError('User name must be unique')

        # use a UUID4 for stable, low-collision ids across files and machines
        user_id = str(uuid4())
        users[user_id] = {
            'id': user_id,
            'name': name,
            'display_name': display_name,
            # creation time stored in ISO8601 (with UTC) for easy parsing/sorting
            'creation_time': datetime.now(timezone.utc).isoformat(),
        }
        self._save_users(users)
        return json.dumps({'id': user_id})

    def list_users(self) -> str:
        """List all users with their stored fields; raises ValueError only on storage or serialization issues."""
        users = self._load_users()
        response = [
            {
                'id': user['id'],
                'name': user['name'],
                'display_name': user['display_name'],
                'creation_time': user['creation_time'],
            }
            for user in users.values()
        ]
        return json.dumps(response)

    def describe_user(self, request: str) -> str:
        """Describe a user by id; raises ValueError if the request is invalid or the user is missing."""
        payload = self._parse_request(request)
        user_id = payload.get('id')
        if not isinstance(user_id, str) or not user_id:
            raise ValueError('User id is required')

        users = self._load_users()
        user = users.get(user_id)
        if user is None:
            raise ValueError('User not found')

        return json.dumps(
            {
                'id': user['id'],
                'name': user['name'],
                'display_name': user['display_name'],
                'creation_time': user['creation_time'],
            }
        )

    def update_user(self, request: str) -> str:
        """Update a user's display name without changing the name; raises ValueError if the user is missing or input is invalid."""
        payload = self._parse_request(request)
        user_id = payload.get('id')
        user_payload = payload.get('user')

        if not isinstance(user_id, str) or not user_id:
            raise ValueError('User id is required')
        if not isinstance(user_payload, dict):
            raise ValueError('User details are required')

        display_name = user_payload.get('display_name')
        if not isinstance(display_name, str):
            raise ValueError('Display name is required')
        if len(display_name) > 128:
            raise ValueError('Display name can be at most 128 characters')

        users = self._load_users()
        user = users.get(user_id)
        if user is None:
            raise ValueError('User not found')

        user['display_name'] = display_name
        self._save_users(users)
        return json.dumps({'id': user_id})

    def get_user_teams(self, request: str) -> str:
        """List teams for a user by scanning teams.json; raises ValueError if the request is invalid or the user is missing."""
        payload = self._parse_request(request)
        user_id = payload.get('id')
        if not isinstance(user_id, str) or not user_id:
            raise ValueError('User id is required')

        users = self._load_users()
        if user_id not in users:
            raise ValueError('User not found')

        teams = self._storage.load('teams')
        response = []
        for team in teams.values():
            members = team.get('members', [])
            if user_id in members:
                response.append(
                    {
                        'name': team.get('name'),
                        'description': team.get('description'),
                        'creation_time': team.get('creation_time'),
                    }
                )
        return json.dumps(response)