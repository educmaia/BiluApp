# auth.py - Reescrito com a biblioteca ldap3 para compatibilidade com Windows
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
from ldap3 import Server, Connection, ALL, NTLM, Tls
from ldap3.core.exceptions import LDAPInvalidCredentialsResult, LDAPSocketOpenError, LDAPException

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBasic()


def authenticate_ad(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Autentica um usuário no Active Directory do IFSP usando a biblioteca ldap3.
    Esta abordagem é puramente em Python e não requer compilação.
    """
    # Configurações do servidor AD do IFSP
    # O uso de 'ad.ifsp.edu.br' e a porta 636 (LDAPS) são mais seguros.
    # use_ssl=True garante que a comunicação seja criptografada.
    server_uri = "ldaps://ad.ifsp.edu.br:636"
    server = Server(server_uri, get_info=ALL, use_ssl=True)

    # Formato do nome de usuário para autenticação no AD da Microsoft
    user_dn = f"{credentials.username}@ifsp.edu.br"
    password = credentials.password

    conn = None
    try:
        # Tenta estabelecer uma conexão com o servidor AD
        # O client_strategy=NTLM pode ser necessário em algumas configurações de AD
        conn = Connection(server, user=user_dn, password=password,
                          authentication=NTLM, auto_bind=True)

        # Se o auto_bind=True for bem-sucedido, a conexão está autenticada.
        # Agora, vamos buscar os detalhes do usuário.
        search_base = "DC=ifsp,DC=edu,DC=br"
        search_filter = f"(sAMAccountName={credentials.username})"

        # Atributos que queremos extrair do AD
        attributes = ['displayName', 'mail',
                      'department', 'cn', 'givenName', 'sn']

        # Executa a busca
        conn.search(search_base, search_filter, attributes=attributes)

        # Verifica se a busca retornou algum resultado
        if not conn.entries or len(conn.entries) == 0:
            logger.warning(
                f"Usuário {credentials.username} autenticado, mas não encontrado na busca no AD.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado no diretório após autenticação."
            )

        # Extrai os dados do primeiro resultado encontrado
        user_data = conn.entries[0]

        # Constrói a resposta com os dados do usuário
        user_info = {
            "username": credentials.username,
            "nome": str(user_data.displayName or user_data.cn or f"{user_data.givenName} {user_data.sn}"),
            "email": str(user_data.mail or f"{credentials.username}@ifsp.edu.br"),
            "setor": str(user_data.department or "Não informado")
        }

        logger.info(
            f"Autenticação bem-sucedida para o usuário: {credentials.username}")
        return user_info

    except LDAPInvalidCredentialsResult:
        logger.warning(
            f"Credenciais inválidas para o usuário: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    except LDAPSocketOpenError as e:
        logger.error(f"Não foi possível conectar ao servidor LDAP: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servidor de autenticação indisponível. Verifique a conexão de rede ou o endereço do servidor."
        )
    except LDAPException as e:
        logger.error(f"Ocorreu um erro LDAP geral: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno de autenticação: {e}"
        )
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado na autenticação: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro inesperado no servidor durante a autenticação."
        )
    finally:
        # Garante que a conexão seja fechada
        if conn and conn.bound:
            conn.unbind()


def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Wrapper para autenticação que pode ser usado como dependência
    em outros endpoints que precisam de autenticação.
    """
    return authenticate_ad(credentials)
