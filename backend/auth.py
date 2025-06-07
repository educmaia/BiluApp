# auth.py - Integração com AD do IFSP
import ldap
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBasic()


def authenticate_ad(credentials: HTTPBasicCredentials = Depends(security)):
    conn = None
    try:
        # Configurar para o AD do IFSP
        ldap_server = "ldap://ad.ifsp.edu.br"
        ldap_base_dn = "DC=ifsp,DC=edu,DC=br"

        # Inicializar conexão LDAP
        conn = ldap.initialize(ldap_server)
        conn.set_option(ldap.OPT_REFERRALS, 0)  # Importante para AD
        conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)  # Use LDAP v3

        # Autenticar usuário
        user_dn = f"{credentials.username}@ifsp.edu.br"
        conn.simple_bind_s(user_dn, credentials.password)

        # Buscar informações do usuário
        search_filter = f"(sAMAccountName={credentials.username})"
        attributes = ['displayName', 'mail',
                      'department', 'cn', 'givenName', 'sn']

        result = conn.search_s(
            ldap_base_dn,
            ldap.SCOPE_SUBTREE,
            search_filter,
            attributes
        )

        # Verificar se usuário foi encontrado
        if not result or len(result) == 0:
            logger.warning(
                f"Usuário {credentials.username} não encontrado no AD")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado no diretório"
            )

        # Extrair dados do usuário com verificações de segurança
        user_data = result[0][1]

        def get_attr_value(attr_name: str, default: str = "Não informado") -> str:
            """Extrai valor do atributo LDAP com tratamento de erros"""
            try:
                if attr_name in user_data and user_data[attr_name]:
                    return user_data[attr_name][0].decode('utf-8')
                return default
            except (IndexError, UnicodeDecodeError, AttributeError):
                return default

        # Construir resposta com dados do usuário
        user_info = {
            "username": credentials.username,
            "nome": get_attr_value('displayName',
                                   get_attr_value('cn',
                                                  f"{get_attr_value('givenName')} {get_attr_value('sn')}")),
            "email": get_attr_value('mail', f"{credentials.username}@ifsp.edu.br"),
            "setor": get_attr_value('department', "IFSP")
        }

        logger.info(
            f"Autenticação bem-sucedida para usuário: {credentials.username}")
        return user_info

    except ldap.INVALID_CREDENTIALS:
        logger.warning(
            f"Credenciais inválidas para usuário: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )

    except ldap.SERVER_DOWN:
        logger.error("Servidor LDAP indisponível")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servidor de autenticação indisponível"
        )

    except ldap.TIMEOUT:
        logger.error("Timeout na conexão LDAP")
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Timeout na autenticação"
        )

    except ldap.LDAPError as e:
        logger.error(f"Erro LDAP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno de autenticação"
        )

    except Exception as e:
        logger.error(f"Erro inesperado na autenticação: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno do servidor"
        )

    finally:
        # Garantir que a conexão seja fechada
        if conn:
            try:
                conn.unbind_s()
            except Exception as e:
                logger.warning(f"Erro ao fechar conexão LDAP: {str(e)}")


def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Wrapper para autenticação que pode ser usado como dependência
    em outros endpoints que precisam de autenticação
    """
    return authenticate_ad(credentials)
