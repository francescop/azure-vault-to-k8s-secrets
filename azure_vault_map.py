#!/usr/bin/python3

import asyncio
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.keyvault.secrets import SecretClient
from kubernetes import client as kubernetes_client
from kubernetes import config as kubernetes_config
import logging
import os
import base64
import inflection
import time

LOGLEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()
DRY_RUN = os.environ.get('DRY_RUN', False)
UPDATE_FREQUENCY_IN_S = os.environ.get('UPDATE_FREQUENCY_IN_S', 60)

logging.basicConfig(level=LOGLEVEL)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity._internal.get_token_mixin").setLevel(logging.WARNING)

AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID', None)
AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET', None)
AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID', None)

async def get_azure_credentials():
    """ get azure credentials """
    azure_credentials = None

    # if azure credentials are set via env var use them
    if(AZURE_CLIENT_ID is not None and
            AZURE_CLIENT_SECRET is not None and
            AZURE_TENANT_ID is not None):
        azure_credentials = ClientSecretCredential(
                tenant_id=AZURE_TENANT_ID,
                client_id=AZURE_CLIENT_ID,
                client_secret=AZURE_CLIENT_SECRET)
    else:
        try:
            azure_credentials = DefaultAzureCredential()
        except Exception as err:
            logging.error('can not get credentials: %s', err)

    return azure_credentials

async def main():
    while True:
        # read secrets from azure
        azure_credentials = await get_azure_credentials()

        # get namespace from env var, else use 'default' namespace
        namespace = os.environ.get('NAMESPACE', 'default')

        try:
            # loca cluster config - running in a kubernetes cluster
            kubernetes_config.load_incluster_config()

            # get current namespace
            with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as file:
                namespace = file.read()
        except kubernetes_config.ConfigException:
            try:
                kubernetes_config.load_kube_config()
            except kubernetes_config.ConfigException:
                raise Exception("Could not configure kubernetes python client")

        core_api = kubernetes_client.CoreV1Api()

        namespace_secrets = core_api.list_namespaced_secret(namespace)

        for secret in namespace_secrets.items:
            try:
                if 'get-secrets-from-vault' in secret.metadata.annotations:
                    vault_url = secret.metadata.annotations['get-secrets-from-vault']

                    logging.info('getting data for %s/%s from %s',
                            namespace,
                            secret.metadata.name,
                            vault_url)

                    secret_client = SecretClient(vault_url, azure_credentials)
                    new_secrets = kubernetes_client.V1Secret()

                    convert_camel_case_to_snake_case = 'get-secrets-from-vault-camel-to-snake-case' in secret.metadata.annotations
                    convert_lower_to_upper_case = 'get-secrets-from-vault-lower-to-upper-case' in secret.metadata.annotations
                    new_secrets.data = await get_and_prepare_vault_secrets(
                            secret_client,
                            convert_camel_case_to_snake_case,
                            convert_lower_to_upper_case
                            )

                    current_secret_data = core_api.read_namespaced_secret(
                            secret.metadata.name,
                            namespace).data

                    if current_secret_data != new_secrets.data:
                        if DRY_RUN is False:
                            await replace_secret(core_api, secret, new_secrets)
                        else:
                            logging.warning('[DRY_RUN] %s/%s would have changed',
                            namespace,
                            secret.metadata.name)
                    else:
                        logging.info("no changes %s/%s - %s",
                                secret.metadata.namespace,
                                secret.metadata.name,
                                secret.metadata.annotations['get-secrets-from-vault'])
            except TypeError:
                pass
            except Exception as err:
                logging.error(err)

        time.sleep(int(UPDATE_FREQUENCY_IN_S))


async def get_and_prepare_vault_secrets(
        secret_client,
        convert_camel_case_to_snake_case,
        convert_lower_to_upper_case):
    """
    - get secrets from azure
    - convert secret name from camel case to snake case if needed
    - convert secret name from lower case to upper case if needed
    - encode in base64
    """
    secret_properties = secret_client.list_properties_of_secrets()

    data = {}

    for secret_property in secret_properties:
        # the list doesn't include values or versions of the secrets
        try:
            if secret_property.enabled:
                properties = secret_client.get_secret(secret_property.name)
                secret_name = secret_property.name

                if convert_camel_case_to_snake_case:
                    secret_name = inflection.underscore(secret_name)
                    logging.debug("convert_camel_case_to_snake_case %s - %s",
                            secret_property.name,
                            secret_name)

                if convert_lower_to_upper_case:
                    secret_name = secret_name.upper()
                    logging.debug("convert_lower_to_upper_case %s - %s",
                            secret_property.name,
                            secret_name)

                data[secret_name] = base64.b64encode(properties.value.encode()).decode()
        except Exception as err:
            logging.error(err)
    return data

async def replace_secret(core_api, secret, new_secrets):
    """ replaces k8s secret with azure vault secrets """
    logging.debug('processing {secret.metadata.namespace}/{secret.metadata.name}')
    try:
        new_secrets.metadata = secret.metadata
        core_api.replace_namespaced_secret(
                secret.metadata.name,
                secret.metadata.namespace,
                new_secrets)
        logging.info("updated %s/%s - %s",
                secret.metadata.namespace,
                secret.metadata.name,
                secret.metadata.annotations['get-secrets-from-vault'])
    except Exception as err:
        logging.error(err)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
