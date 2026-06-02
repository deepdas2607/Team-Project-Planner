from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from factwise.storage import JSONStorage
from team_base import TeamBase


class TeamImpl(TeamBase):
    def __init__(self) -> None:
        """Initialize JSON storage for team persistence; raises no exceptions."""
        self._storage = JSONStorage()

    def _load_teams(self) -> dict[str, dict]:
        """Load stored teams from teams.json; raises ValueError if storage data is invalid."""
        return self._storage.load('teams')

    def _save_teams(self, teams: dict[str, dict]) -> None:
        """Persist teams to teams.json; raises ValueError if the data cannot be serialized."""
        self._storage.save('teams', teams)

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
        """Validate a team name; raises ValueError if the name is missing or too long."""
        if not isinstance(value, str) or not value:
            # team must have a short non-empty name
            raise ValueError('Team name is required')
        if len(value) > 64:
            # keep team names concise for display
            raise ValueError('Team name can be at most 64 characters')
        return value

    def _validate_description(self, value: object) -> str:
        """Validate a team description; raises ValueError if the description is invalid or too long."""
        if not isinstance(value, str):
            raise ValueError('Description is required')
        if len(value) > 128:
            raise ValueError('Description can be at most 128 characters')
        return value

    def _ensure_user_exists(self, user_id: object) -> str:
        """Validate that a user exists; raises ValueError if the user id is invalid or missing."""
        if not isinstance(user_id, str) or not user_id:
            raise ValueError('User id is required')
        users = self._load_users()
        if user_id not in users:
            raise ValueError('User not found')
        return user_id

    def create_team(self, request: str) -> str:
        """Create a team and return its id; raises ValueError for invalid input or missing admin/user constraints."""
        payload = self._parse_request(request)
        name = self._validate_name(payload.get('name'))
        description = self._validate_description(payload.get('description'))
        admin = self._ensure_user_exists(payload.get('admin'))

        teams = self._load_teams()
        if any(team.get('name') == name for team in teams.values()):
            raise ValueError('Team name must be unique')

        # use UUID4 to generate a globally unique id for the team
        team_id = str(uuid4())
        teams[team_id] = {
            'id': team_id,
            'name': name,
            'description': description,
            'admin': admin,
            # store creation time in ISO8601 UTC for easy sorting and comparison
            'creation_time': datetime.now(timezone.utc).isoformat(),
            'members': [admin],
        }
        self._save_teams(teams)
        return json.dumps({'id': team_id})

    def list_teams(self) -> str:
        """List teams and return their public fields; raises ValueError only if storage cannot be read."""
        teams = self._load_teams()
        response = [
            {
                'id': team.get('id'),
                'name': team.get('name'),
                'description': team.get('description'),
                'creation_time': team.get('creation_time'),
                'admin': team.get('admin'),
            }
            for team in teams.values()
        ]
        return json.dumps(response)

    def describe_team(self, request: str) -> str:
        """Describe a team by id; raises ValueError for invalid input or when the team is missing."""
        payload = self._parse_request(request)
        team_id = payload.get('id')
        if not isinstance(team_id, str) or not team_id:
            raise ValueError('Team id is required')

        teams = self._load_teams()
        team = teams.get(team_id)
        if team is None:
            raise ValueError('Team not found')

        return json.dumps(
            {
                'name': team.get('name'),
                'description': team.get('description'),
                'creation_time': team.get('creation_time'),
                'admin': team.get('admin'),
            }
        )

    def update_team(self, request: str) -> str:
        """Update a team and return its id; raises ValueError for invalid input or when the team is missing."""
        payload = self._parse_request(request)
        team_id = payload.get('id')
        team_payload = payload.get('team')

        if not isinstance(team_id, str) or not team_id:
            raise ValueError('Team id is required')
        if not isinstance(team_payload, dict):
            raise ValueError('Team details are required')

        teams = self._load_teams()
        team = teams.get(team_id)
        if team is None:
            raise ValueError('Team not found')

        name = self._validate_name(team_payload.get('name', team.get('name')))
        description = self._validate_description(team_payload.get('description', team.get('description')))
        admin = team_payload.get('admin', team.get('admin'))
        if admin is not None:
            admin = self._ensure_user_exists(admin)

        if any(existing_id != team_id and existing.get('name') == name for existing_id, existing in teams.items()):
            raise ValueError('Team name must be unique')

        team['name'] = name
        team['description'] = description
        if admin is not None:
            team['admin'] = admin
            members = team.setdefault('members', [])
            if admin not in members:
                members.insert(0, admin)

        self._save_teams(teams)
        return json.dumps({'id': team_id})

    def add_users_to_team(self, request: str):
        """Add users to a team; raises ValueError for invalid input, missing users, or membership cap violations."""
        payload = self._parse_request(request)
        team_id = payload.get('id')
        users_to_add = payload.get('users')

        if not isinstance(team_id, str) or not team_id:
            raise ValueError('Team id is required')
        if not isinstance(users_to_add, list):
            raise ValueError('Users must be a list')
        # the request itself should not try to add more than 50 users at once
        if len(users_to_add) > 50:
            raise ValueError('Team member cap exceeded')

        teams = self._load_teams()
        team = teams.get(team_id)
        if team is None:
            raise ValueError('Team not found')

        users = self._load_users()
        members = team.setdefault('members', [])
        new_user_ids: list[str] = []
        for user_id in users_to_add:
            if not isinstance(user_id, str) or not user_id:
                # each added member must be a non-empty string id
                raise ValueError('User id is required')
            if user_id not in users:
                # user must exist before being added to a team
                raise ValueError('User not found')
            if user_id not in members and user_id not in new_user_ids:
                new_user_ids.append(user_id)

        # enforce a practical member cap to avoid huge teams in the JSON file
        if len(members) + len(new_user_ids) > 50:
            raise ValueError('Team member cap exceeded')

        members.extend(new_user_ids)
        self._save_teams(teams)
        return json.dumps({'id': team_id})

    def remove_users_from_team(self, request: str):
        """Remove users from a team; raises ValueError for invalid input or when the team is missing."""
        payload = self._parse_request(request)
        team_id = payload.get('id')
        users_to_remove = payload.get('users')

        if not isinstance(team_id, str) or not team_id:
            raise ValueError('Team id is required')
        if not isinstance(users_to_remove, list):
            raise ValueError('Users must be a list')

        teams = self._load_teams()
        team = teams.get(team_id)
        if team is None:
            raise ValueError('Team not found')

        members = team.setdefault('members', [])
        admin = team.get('admin')
        # the admin is required for team ownership, so removing them should fail
        if admin in users_to_remove:
            raise ValueError('Admin cannot be removed from the team')
        team['members'] = [member for member in members if member not in users_to_remove or member == admin]
        self._save_teams(teams)
        return json.dumps({'id': team_id})

    def list_team_users(self, request: str):
        """List the members of a team; raises ValueError for invalid input or when the team is missing."""
        payload = self._parse_request(request)
        team_id = payload.get('id')
        if not isinstance(team_id, str) or not team_id:
            raise ValueError('Team id is required')

        teams = self._load_teams()
        team = teams.get(team_id)
        if team is None:
            raise ValueError('Team not found')

        users = self._load_users()
        response = []
        for user_id in team.get('members', []):
            user = users.get(user_id)
            if user is not None:
                response.append(
                    {
                        'id': user_id,
                        'name': user.get('name'),
                        'display_name': user.get('display_name'),
                    }
                )
        return json.dumps(response)