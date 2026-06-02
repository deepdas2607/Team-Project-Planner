from __future__ import annotations

import json
from typing import Any
from uuid import uuid4
from pathlib import Path

import requests


BASE_URL = 'http://127.0.0.1:8000'
RUN_TAG = uuid4().hex[:8]
DB_DIR = Path(__file__).resolve().parent / 'db'


def request_json(method: str, path: str, payload: dict[str, Any] | None = None, params: dict[str, Any] | None = None):
	url = f'{BASE_URL}{path}'
	response = requests.request(method, url, json=payload, params=params, timeout=10)
	try:
		body = response.json()
	except ValueError:
		body = response.text
	return response, body


def print_result(name: str, passed: bool, expected: str, received: str) -> bool:
	status = 'PASS' if passed else 'FAIL'
	print(f'{status} - {name}')
	if not passed:
		print(f'  expected: {expected}')
		print(f'  received: {received}')
	return passed


def body_repr(body: Any) -> str:
	if isinstance(body, (dict, list)):
		return json.dumps(body, ensure_ascii=True)
	return repr(body)


def list_data(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	response, body = request_json('GET', path, params=params)
	if response.status_code == 200 and isinstance(body, list):
		return body
	return []


def ensure_user(name: str, display_name: str) -> str:
	for user in list_data('/api/users/'):
		if user.get('name') == name and user.get('id'):
			return user['id']
	response, body = request_json('POST', '/api/users/', {'name': name, 'display_name': display_name})
	if response.status_code >= 400 or not isinstance(body, dict) or not body.get('id'):
		raise RuntimeError(f'Could not create user {name}: {body_repr(body)}')
	return body['id']


def ensure_team(name: str, description: str, admin_id: str) -> str:
	for team in list_data('/api/teams/'):
		team_id = team.get('id')
		if team.get('name') == name and team_id:
			if team.get('admin') != admin_id:
				response, body = request_json(
					'PUT',
					f'/api/teams/{team_id}/',
					{'team': {'name': name, 'description': description, 'admin': admin_id}},
				)
				if response.status_code >= 400:
					raise RuntimeError(f'Could not update team {name}: {body_repr(body)}')
			return team_id
	response, body = request_json('POST', '/api/teams/', {'name': name, 'description': description, 'admin': admin_id})
	if response.status_code >= 400 or not isinstance(body, dict) or not body.get('id'):
		raise RuntimeError(f'Could not create team {name}: {body_repr(body)}')
	return body['id']


def ensure_board(name: str, description: str, team_id: str) -> str:
	for board in list_data('/api/boards/', params={'team_id': team_id}):
		if board.get('name') == name and board.get('id'):
			return board['id']
	response, body = request_json(
		'POST',
		'/api/boards/',
		{'name': name, 'description': description, 'team_id': team_id, 'creation_time': '2026-05-21T00:00:00+00:00'},
	)
	if response.status_code >= 400 or not isinstance(body, dict) or not body.get('id'):
		raise RuntimeError(f'Could not create board {name}: {body_repr(body)}')
	return body['id']


def reset_local_store() -> None:
	DB_DIR.mkdir(exist_ok=True)
	for filename in ('users.json', 'teams.json', 'boards.json'):
		path = DB_DIR / filename
		path.write_text('{}', encoding='utf-8')


def main() -> None:
	passed_count = 0
	total_count = 0

	# Setup data used by the ordered tests below.
	reset_local_store()
	alice_id = ensure_user('testuser_alice', 'Alice')
	bob_id = ensure_user('testuser_bob', 'Bob')
	team_name = f'Test Team {RUN_TAG}'
	team_id = ensure_team(team_name, team_name, alice_id)
	_, _ = request_json('POST', f'/api/teams/{team_id}/members/', {'users': [bob_id]})
	board_name = f'Test Board {RUN_TAG}'
	board_id = ensure_board(board_name, board_name, team_id)

	_, task1_body = request_json(
		'POST',
		'/api/tasks/',
		{
			'board_id': board_id,
			'title': 'Task 1',
			'description': 'First task',
			'user_id': alice_id,
			'creation_time': '2026-05-21T00:00:00+00:00',
		},
	)
	task1_id = task1_body.get('id') if isinstance(task1_body, dict) else None
	_, task2_body = request_json(
		'POST',
		'/api/tasks/',
		{
			'board_id': board_id,
			'title': 'Task 2',
			'description': 'Second task',
			'user_id': alice_id,
			'creation_time': '2026-05-21T00:01:00+00:00',
		},
	)
	task2_id = task2_body.get('id') if isinstance(task2_body, dict) else None

	# Test 1 - duplicate usernames should be rejected.
	total_count += 1
	response, body = request_json('POST', '/api/users/', {'name': 'testuser_alice', 'display_name': 'Alice Again'})
	if print_result(
		'Duplicate user name should return 400',
		response.status_code == 400,
		'HTTP 400',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 2 - overly long names should fail validation.
	total_count += 1
	response, body = request_json('POST', '/api/users/', {'name': 'a' * 65, 'display_name': 'Too Long'})
	if print_result(
		'Name over 64 chars should return 400',
		response.status_code == 400,
		'HTTP 400',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 3 - listing users should return a JSON array.
	total_count += 1
	response, body = request_json('GET', '/api/users/')
	passed = response.status_code == 200 and isinstance(body, list)
	if print_result(
		'List users should return array',
		passed,
		'HTTP 200 with a list response',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 4 - describe should return the stored user name.
	total_count += 1
	response, body = request_json('GET', f'/api/users/{alice_id}/')
	passed = response.status_code == 200 and isinstance(body, dict) and body.get('name') == 'testuser_alice'
	if print_result(
		'Describe user should return correct name',
		passed,
		'HTTP 200 and name == testuser_alice',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 5 - update should change display_name.
	total_count += 1
	response, body = request_json('PUT', f'/api/users/{alice_id}/', {'user': {'display_name': 'Alice Updated'}})
	if print_result(
		'Update user display_name should work',
		response.status_code == 200,
		'HTTP 200',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 6 - user teams should include the team created during setup.
	total_count += 1
	response, body = request_json('GET', f'/api/users/{alice_id}/teams/')
	passed = response.status_code == 200 and isinstance(body, list) and len(body) >= 1
	if print_result(
		"Get user teams should return alice's team",
		passed,
		'HTTP 200 with at least one team',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 7 - team listing should return a JSON array.
	total_count += 1
	response, body = request_json('GET', '/api/teams/')
	passed = response.status_code == 200 and isinstance(body, list)
	if print_result(
		'List teams should return array',
		passed,
		'HTTP 200 with a list response',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 8 - board listing should find the board created in setup.
	total_count += 1
	response, body = request_json('GET', '/api/boards/', params={'team_id': team_id})
	passed = response.status_code == 200 and isinstance(body, list) and len(body) >= 1
	if print_result(
		'List boards for team should return our board',
		passed,
		'HTTP 200 with at least one board',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 9 - closing a board with open tasks should fail.
	total_count += 1
	response, body = request_json('POST', f'/api/boards/{board_id}/', {'action': 'close'})
	if print_result(
		'Close board with incomplete tasks should return 400',
		response.status_code == 400,
		'HTTP 400',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 10 - first task should transition to COMPLETE.
	total_count += 1
	response, body = request_json('PUT', '/api/tasks/status/', {'id': task1_id, 'status': 'COMPLETE'})
	if print_result(
		'Update task 1 to COMPLETE should work',
		response.status_code == 200,
		'HTTP 200',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 11 - second task should also transition to COMPLETE.
	total_count += 1
	response, body = request_json('PUT', '/api/tasks/status/', {'id': task2_id, 'status': 'COMPLETE'})
	if print_result(
		'Update task 2 to COMPLETE should work',
		response.status_code == 200,
		'HTTP 200',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 12 - closing should succeed once every task is complete.
	total_count += 1
	response, body = request_json('POST', f'/api/boards/{board_id}/', {'action': 'close'})
	if print_result(
		'Close board with all tasks complete should work',
		response.status_code == 200,
		'HTTP 200',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 13 - closed boards should reject new tasks.
	total_count += 1
	response, body = request_json(
		'POST',
		'/api/tasks/',
		{
			'board_id': board_id,
			'title': 'Task after close',
			'description': 'Should fail',
			'user_id': alice_id,
			'creation_time': '2026-05-21T00:02:00+00:00',
		},
	)
	if print_result(
		'Add task to CLOSED board should return 400',
		response.status_code == 400,
		'HTTP 400',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 14 - admin removal should be blocked.
	total_count += 1
	response, body = request_json('DELETE', f'/api/teams/{team_id}/members/', {'users': [alice_id]})
	if print_result(
		'Remove admin from team should return 400',
		response.status_code == 400,
		'HTTP 400',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 15 - member cap should reject adding too many users at once.
	bulk_ids: list[str] = []
	for index in range(51):
		_, bulk_body = request_json('POST', '/api/users/', {'name': f'bulkuser_{index}', 'display_name': f'Bulk {index}'})
		if isinstance(bulk_body, dict) and bulk_body.get('id'):
			bulk_ids.append(bulk_body['id'])
	total_count += 1
	response, body = request_json('POST', f'/api/teams/{team_id}/members/', {'users': bulk_ids})
	if print_result(
		'Add 51 users to team should return 400',
		response.status_code == 400,
		'HTTP 400',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	# Test 16 - export should create a downloadable board report.
	total_count += 1
	response, body = request_json('POST', f'/api/boards/{board_id}/export/', {})
	passed = response.status_code == 200 and isinstance(body, dict) and 'out_file' in body
	if print_result(
		'Export board should create a file',
		passed,
		'HTTP 200 with an out_file key',
		f'HTTP {response.status_code}, body={body_repr(body)}',
	):
		passed_count += 1

	print(f'Results: {passed_count}/{total_count} passed')


if __name__ == '__main__':
	main()