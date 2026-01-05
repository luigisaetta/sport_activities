"""
File name: config.py
Author: Luigi Saetta
Date last modified: 2025-07-02
Python Version: 3.11

Description:
    This module provides general configurations


Usage:
    Import this module into other scripts to use its functions.
    Example:
        import config

License:
    This code is released under the MIT License.

Notes:
    This is a part of a demo showing how to implement an advanced
    RAG solution as a LangGraph agent.

Warnings:
    This module is in development, may change in future versions.
"""

DEBUG = False
STREAMING = False
USERNAME = "Luigi"

# type of OCI auth
AUTH = "API_KEY"

# embeddings
# added this to distinguish between Cohere and REST NVIDIA models
# can be OCI or NVIDIA
EMBED_MODEL_TYPE = "OCI"
# EMBED_MODEL_TYPE = "NVIDIA"
EMBED_MODEL_ID = "cohere.embed-multilingual-v3.0"

# this one needs to specify the dimension, default is 1536
# EMBED_MODEL_ID = "cohere.embed-v4.0"
# used only for NVIDIA models
NVIDIA_EMBED_MODEL_URL = ""


# LLM
# this is the default model
LLM_MODEL_ID = "xai.grok-4"
TEMPERATURE = 0.0
TOP_P = 1
MAX_TOKENS = 4000

# OCI general
REGION = "eu-frankfurt-1"

# (11/12/2025) introduced to support the switch to langchain OpenAI integration
USE_LANGCHAIN_OPENAI = False

# REGION = "us-chicago-1"
SERVICE_ENDPOINT = f"https://inference.generativeai.{REGION}.oci.oraclecloud.com"

if REGION == "us-chicago-1":
    # for now only available in chicago region
    MODEL_LIST = [
        "xai.grok-4",
        "xai.grok-4-fast-reasoning",
        "meta.llama-4-maverick-17b-128e-instruct-fp8",
        "openai.gpt-4.1",
        "openai.gpt-4o",
        "openai.gpt-5",
        "openai.gpt-oss-120b",
        "google.gemini-2.5-pro",
    ]
else:
    MODEL_LIST = [
        "openai.gpt-4.1",
        "openai.gpt-5",
        "openai.gpt-oss-120b",
        "meta.llama-3.3-70b-instruct",
    ]

# semantic search
TOP_K = 6
COLLECTION_LIST = ["BOOKS", "NVIDIA_BOOKS2"]
DEFAULT_COLLECTION = "BOOKS"


# history management (put -1 if you want to disable trimming)
# consider that we have pair (human, ai) so use an even (ex: 6) value
MAX_MSGS_IN_HISTORY = 20

# reranking enabled or disabled from UI

# for loading
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 100

# for MCP server
TRANSPORT = "streamable-http"
# bind to all interfaces
HOST = "0.0.0.0"
PORT = 9000

# with this we can toggle JWT token auth
ENABLE_JWT_TOKEN = True

# can be OCI_IAM or IBM_CONTEXT_FORGE
# JWT_TOKEN_PROVIDER = "IBM_CONTEXT_FORGE"
JWT_TOKEN_PROVIDER = "OCI_IAM"

# for OCI_IAM put your domain URL here
IAM_BASE_URL = "https://idcs-930d7b2ea2cb46049963ecba3049f509.identity.oraclecloud.com"
# these are used during the verification of the token
ISSUER = "https://identity.oraclecloud.com/"
AUDIENCE = ["urn:opc:lbaas:logicalguid=idcs-930d7b2ea2cb46049963ecba3049f509"]

# for Select AI
# SELECT_AI_PROFILE = "OCI_GENERATIVE_AI_PROFILE_F1"
# this one with SH schema
SELECT_AI_PROFILE = "OCI_GENERATIVE_AI_PROFILE_BANKS"

# APM integration
ENABLE_TRACING = False
OTEL_SERVICE_NAME = "llm-mcp-agent"
OCI_APM_TRACES_URL = "https://aaaadec2jjn3maaaaaaaaach4e.apm-agt.eu-frankfurt-1.oci.oraclecloud.com/20200101/opentelemetry/private/v1/traces"

# UI
UI_TITLE = "🛠️ AI Assistant powered by MCP"

# Agent API
AGENT_API_HOST = "0.0.0.0"
AGENT_API_PORT = 8001

# Github integration
GITHUB_DEFAULT_REPO = "mcp-oci-integration"
