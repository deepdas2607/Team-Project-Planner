from __future__ import annotations

import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from factwise.impl.board_impl import ProjectBoardImpl as BoardImpl
from factwise.impl.team_impl import TeamImpl
from factwise.impl.user_impl import UserImpl


user_api = UserImpl()
team_api = TeamImpl()
board_api = BoardImpl()


def _json_response(payload: object, status: int = 200) -> JsonResponse:
	return JsonResponse(payload, safe=not isinstance(payload, list), status=status)


def _parse_json_response(response_text: str) -> object:
	return json.loads(response_text)


def _request_body_text(request) -> str:
	# read the raw request body as text; views use JSON strings passed to the implementation
	return request.body.decode('utf-8') if request.body else ''


def _request_query_json(request, extra: dict[str, object] | None = None) -> str:
	payload = {key: value for key, value in request.GET.items()}
	if extra:
		payload.update(extra)
	return json.dumps(payload)


@method_decorator(csrf_exempt, name='dispatch')
class UserListView(View):
	def get(self, request):
		# try/except maps ValueError -> 400 and other exceptions to 500
		try:
			return _json_response(_parse_json_response(user_api.list_users()))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)

	def post(self, request):
		try:
			return _json_response(_parse_json_response(user_api.create_user(_request_body_text(request))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class UserDetailView(View):
	def get(self, request, id):
		try:
			return _json_response(_parse_json_response(user_api.describe_user(json.dumps({'id': id}))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)

	def put(self, request, id):
		try:
			payload = json.loads(_request_body_text(request) or '{}')
			payload['id'] = id
			return _json_response(_parse_json_response(user_api.update_user(json.dumps(payload))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class UserTeamsView(View):
	def get(self, request, id):
		try:
			return _json_response(_parse_json_response(user_api.get_user_teams(json.dumps({'id': id}))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TeamListView(View):
	def get(self, request):
		try:
			return _json_response(_parse_json_response(team_api.list_teams()))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)

	def post(self, request):
		try:
			return _json_response(_parse_json_response(team_api.create_team(_request_body_text(request))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TeamDetailView(View):
	def get(self, request, id):
		try:
			return _json_response(_parse_json_response(team_api.describe_team(json.dumps({'id': id}))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)

	def put(self, request, id):
		try:
			payload = json.loads(_request_body_text(request) or '{}')
			payload['id'] = id
			return _json_response(_parse_json_response(team_api.update_team(json.dumps(payload))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TeamMembersView(View):
	def post(self, request, id):
		try:
			payload = json.loads(_request_body_text(request) or '{}')
			payload['id'] = id
			return _json_response(_parse_json_response(team_api.add_users_to_team(json.dumps(payload))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)

	def delete(self, request, id):
		try:
			payload = json.loads(_request_body_text(request) or '{}')
			payload['id'] = id
			return _json_response(_parse_json_response(team_api.remove_users_from_team(json.dumps(payload))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TeamUsersListView(View):
	def get(self, request, id):
		try:
			return _json_response(_parse_json_response(team_api.list_team_users(json.dumps({'id': id}))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class BoardListView(View):
	def post(self, request):
		try:
			return _json_response(_parse_json_response(board_api.create_board(_request_body_text(request))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)

	def get(self, request):
		try:
			return _json_response(_parse_json_response(board_api.list_boards(_request_query_json(request, {'id': request.GET.get('team_id')}))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class BoardDetailView(View):
	# views are CSRF-exempt because this API is designed for programmatic JSON clients
	def get(self, request, id):
		return JsonResponse({'error': 'Method not allowed'}, status=405)

	def post(self, request, id):
		try:
			payload = json.loads(_request_body_text(request) or '{}')
			action = payload.get('action', 'close')
			if action != 'close':
				raise ValueError('Unsupported action')
			return _json_response(_parse_json_response(board_api.close_board(json.dumps({'id': id}))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class BoardExportView(View):
	def post(self, request, id):
		try:
			return _json_response(_parse_json_response(board_api.export_board(json.dumps({'id': id}))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TaskView(View):
	def post(self, request):
		try:
			return _json_response(_parse_json_response(board_api.add_task(_request_body_text(request))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TaskStatusView(View):
	def _update_status(self, request):
		try:
			return _json_response(_parse_json_response(board_api.update_task_status(_request_body_text(request))))
		except ValueError as exc:
			return JsonResponse({'error': str(exc)}, status=400)
		except Exception:
			return JsonResponse({'error': 'Internal error'}, status=500)

	def put(self, request):
		return self._update_status(request)

	def post(self, request):
		return self._update_status(request)
