import os
from azure.identity import ClientSecretCredential
from azure.ai.projects import AIProjectClient
from openai import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AzureClient:
    """
    Azure client for Azure AI Projects
    """
    def __init__(self):
        """
        Initialize the Azure client
        """
        self.project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
        self.tenant_id = os.getenv("AZURE_AD_TENANT_ID")
        self.client_id = os.getenv("AZURE_AD_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_AD_CLIENT_SECRET")
        self.agent_id = os.getenv("AZURE_AGENT_ID")
        self.project_client = self.setup_azure_client()
        self.agent = self.get_agent()
        self.llm = self.get_llm()

    def setup_azure_client(self):
        """
        Setup the Azure client
        """
        
        # Check for missing environment variables
        missing_vars = []
        if not self.project_endpoint:
            missing_vars.append("AZURE_AI_PROJECT_ENDPOINT")
        if not self.tenant_id:
            missing_vars.append("AZURE_AD_TENANT_ID")
        if not self.client_id:
            missing_vars.append("AZURE_AD_CLIENT_ID")
        if not self.client_secret:
            missing_vars.append("AZURE_AD_CLIENT_SECRET")
        
        if missing_vars:
            error_msg = f"Missing required Azure environment variables: {', '.join(missing_vars)}"
            logger.error(f"ERROR: {error_msg}")
            raise ValueError(error_msg)
        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            self.project_client = AIProjectClient(
                credential=credential,
                endpoint=self.project_endpoint
            )
            logger.info(f"Azure client setup successfully")

            return self.project_client
        except Exception as e:
            error_msg = f"Failed to create Azure client: {str(e)}"
            logger.error(f"ERROR: {error_msg}")
            raise Exception(error_msg)
    
    def get_llm(self):

        llm = AzureOpenAI(
            api_version="2024-12-01-preview",
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            azure_endpoint=os.getenv("AZURE_AI_RESOURCE_ENDPOINT")
        )
        return llm

    def get_agent(self):
        """
        Get the agent from the project client
        """
        agent_id = self.agent_id
        if not agent_id:
            error_msg = "AZURE_AGENT_ID is not set"
            logger.error(f"ERROR: {error_msg}")
            raise ValueError(error_msg)
        try:
            agent = self.project_client.agents.get_agent(agent_id)
            logger.info(f"Agent {agent_id} retrieved successfully")
            return agent
        except Exception as e:
            error_msg = f"Failed to get agent: {str(e)}"
            logger.error(f"ERROR: {error_msg}")
            raise Exception(error_msg)