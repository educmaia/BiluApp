# auth.py - CORRIGIDO para usar a biblioteca ldap3
from ldap3 import Server, Connection, ALL, Tls
from ldap3.core.exceptions import LDAPInvalidCredentialsResult, LDAPSocketOpenError, LDAPBindError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
import ssl

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBasic()


def authenticate_ad(credentials: HTTPBasicCredentials = Depends(security)):
    try:
        # Configurar para o AD do IFSP
        ldap_server_url = "ad.ifsp.edu.br"
        ldap_base_dn = "DC=ifsp,DC=edu,DC=br"

        # Tenta conectar com start_tls
        tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        server = Server(ldap_server_url, get_info=ALL,
                        use_ssl=True, tls=tls_config)

        # Formato do usuário para bind
        user_dn = f"{credentials.username}@ifsp.edu.br"

        # Inicializar conexão LDAP
        # auto_bind=True tenta fazer o bind (autenticação) imediatamente
        conn = Connection(
            server,
            user=user_dn,
            password=credentials.password,
            auto_bind=True,
            raise_exceptions=True  # Importante para capturar erros
        )

        logger.info(
            f"Autenticação bem-sucedida para o usuário: {credentials.username}")

        # Buscar informações adicionais do usuário
        search_filter = f"(sAMAccountName={credentials.username})"
        attributes = ['displayName', 'mail',
                      'department', 'cn', 'givenName', 'sn']

        conn.search(
            search_base=ldap_base_dn,
            search_filter=search_filter,
            attributes=attributes
        )

        # Verificar se o usuário foi encontrado
        if not conn.entries or len(conn.entries) == 0:
            logger.warning(
                f"Usuário {credentials.username} autenticado, mas não encontrado no AD para buscar detalhes.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado no diretório"
            )

        # Extrair dados do usuário do primeiro resultado
        user_entry = conn.entries[0]

        user_info = {
            "username": credentials.username,
            "nome": str(user_entry.displayName or user_entry.cn or f"{user_entry.givenName} {user_entry.sn}"),
            "email": str(user_entry.mail or f"{credentials.username}@ifsp.edu.br"),
            "setor": str(user_entry.department or "IFSP")
        }

        return user_info

    except (LDAPInvalidCredentialsResult, LDAPBindError):
        logger.warning(
            f"Credenciais inválidas para o usuário: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    except LDAPSocketOpenError as e:
        logger.error(f"Servidor LDAP indisponível: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servidor de autenticação indisponível"
        )
    except Exception as e:
        logger.error(f"Erro inesperado na autenticação: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor durante a autenticação"
        )
    finally:
        # Garante que a conexão seja fechada se foi estabelecida
        if 'conn' in locals() and conn.bound:
            conn.unbind()
