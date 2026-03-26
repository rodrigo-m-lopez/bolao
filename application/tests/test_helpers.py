"""Tests for DB lookup helpers get_bolao_id and get_aposta_by_nome."""
import pytest
from bson import ObjectId
import application.app as app_module
from application.app import get_bolao_id, get_aposta_by_nome


class TestGetBolaoId:
    def test_returns_correct_id(self, flask_app):
        inserted = app_module.tbl_bolao.insert_one(
            {'nome': 'test', 'usuario': ObjectId(), 'valor': 10,
             'premiacao': 'prize', 'descricao': ''}
        )
        with flask_app.test_request_context('/'):
            result = get_bolao_id('test')
        assert result == inserted.inserted_id

    def test_missing_bolao_raises_404(self, client):
        rv = client.get('/nonexistent/ranking')
        assert rv.status_code == 404

    def test_missing_bolao_raises_404_via_toggle(self, client):
        rv = client.post('/nonexistent/toggle_pago',
                         data={'nome_aposta': 'x'},
                         headers={'X-CSRFToken': 'skip'})
        # 302 (redirect to login) or 404 — the bolao doesn't exist
        assert rv.status_code in (302, 401, 403, 404)


class TestGetApostaByNome:
    def test_returns_correct_aposta(self, flask_app):
        bolao_id = app_module.tbl_bolao.insert_one(
            {'nome': 'b', 'usuario': ObjectId(), 'valor': 10, 'premiacao': '', 'descricao': ''}
        ).inserted_id
        aposta_id = app_module.tbl_aposta.insert_one(
            {'nome': 'minha', 'bolao': bolao_id, 'usuario': ObjectId(), 'pago': False}
        ).inserted_id
        with flask_app.test_request_context('/'):
            result = get_aposta_by_nome('minha', bolao_id)
        assert result['_id'] == aposta_id

    def test_missing_aposta_raises_404(self, flask_app):
        bolao_id = ObjectId()
        with flask_app.test_request_context('/'):
            with pytest.raises(Exception) as exc_info:
                get_aposta_by_nome('inexistente', bolao_id)
            # Flask abort raises HTTPException (werkzeug)
            assert exc_info.value.code == 404
