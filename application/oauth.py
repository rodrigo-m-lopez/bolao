import json
import logging
import urllib.request
import urllib.error

from rauth import OAuth2Service
from flask import current_app, url_for, request, redirect

logger = logging.getLogger(__name__)


class OAuthSignIn(object):
    providers = None

    def __init__(self, provider_name):
        self.provider_name = provider_name
        credentials = current_app.config['OAUTH_CREDENTIALS'][provider_name]
        self.consumer_id = credentials['id']
        self.consumer_secret = credentials['secret']

    def authorize(self):
        pass

    def callback(self):
        """Return (nome, email, primeiro_nome, sobrenome, foto, sexo) or (None,)*6."""
        return (None,) * 6

    def get_callback_url(self):
        return url_for('oauth_callback', provider=self.provider_name,
                       _external=True)

    @classmethod
    def get_provider(cls, provider_name):
        if cls.providers is None:
            cls.providers = {}
            for provider_class in cls.__subclasses__():
                provider = provider_class()
                cls.providers[provider.provider_name] = provider
        return cls.providers[provider_name]

class GoogleSignIn(OAuthSignIn):
    def __init__(self):
        super(GoogleSignIn, self).__init__('google')
        try:
            googleinfo = urllib.request.urlopen(
                'https://accounts.google.com/.well-known/openid-configuration',
                timeout=10
            )
            google_params = json.load(googleinfo)
        except urllib.error.URLError as exc:
            logger.error('Falha ao buscar configuracao OpenID do Google: %s', exc)
            raise RuntimeError('Nao foi possivel acessar o endpoint de descoberta do Google OAuth') from exc
        self.service = OAuth2Service(
                name='google',
                client_id=self.consumer_id,
                client_secret=self.consumer_secret,
                authorize_url=google_params.get('authorization_endpoint'),
                base_url=google_params.get('userinfo_endpoint'),
                access_token_url=google_params.get('token_endpoint')
        )

    def authorize(self):
        return redirect(self.service.get_authorize_url(
            scope='email',
            response_type='code',
            redirect_uri=self.get_callback_url())
            )

    def callback(self):
        """Return (nome, email, primeiro_nome, sobrenome, foto, sexo) or (None,)*6."""
        if 'code' not in request.args:
            return (None,) * 6
        try:
            oauth_session = self.service.get_auth_session(
                    data={'code': request.args['code'],
                          'grant_type': 'authorization_code',
                          'redirect_uri': self.get_callback_url()
                         },
                    decoder=json.loads
            )
            me = oauth_session.get('').json()
        except Exception as exc:
            logger.error('Falha ao obter dados do usuario no Google: %s', exc)
            return (None,) * 6
        return (me.get('name'),
                me.get('email'),
                me.get('given_name'),
                me.get('family_name'),
                me.get('picture'),
                me.get('gender'))
