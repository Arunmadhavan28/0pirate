export const modelsDocs = `
# 0Pirate: Your Secure AI Gateway for Code

Welcome to the 0Pirate documentation. This guide explains the powerful features of the 0Pirate gateway and details the wide range of AI models you can connect to, from cloud APIs to local, privacy-focused instances.

## More Than a Wrapper: How 0Pirate Protects Your Code

Many tools simply pass your code to an AI model. 0Pirate is fundamentally different. It acts as a sophisticated security and abstraction layer between your valuable source code and the powerful Large Language Models (LLMs) you want to use.

When you submit code to 0Pirate, it never sends your raw, proprietary source code directly to any third-party AI provider. Instead, it undergoes our proprietary **Secure Abstraction Process**.

## The Secure Abstraction Process

Our backend is engineered to ensure a zero-knowledge interaction with the LLM. Here’s what happens every time you run an analysis:

### 1. Secrets & PII Redaction
The first pass scans your code for API keys, passwords, credentials, names, email addresses, and other sensitive personal or infrastructure information. This data is immediately scrubbed.

### 2. Code Abstraction
The core logic of your code is then converted into an abstract, generic representation. Variable names, function names, and comments that could reveal your project's purpose or intellectual property are replaced with non-descript placeholders. The structure and logic are preserved, but the context and identity are removed.

### 3. Task-Specific Prompt Engineering
0Pirate intelligently crafts a highly optimized prompt around your abstracted code. A "Fix & Secure" prompt is vastly different from an "Add Documentation" prompt, ensuring you get the most accurate and relevant results from the LLM.

### 4. Intelligent Model Routing
Your request is sent to the AI provider you selected (OpenAI, Google Gemini, Anthropic, or your local Ollama instance). The AI model works only on the secure, abstract representation of your code.

### 5. De-Abstraction and Validation
When the AI returns a result, 0Pirate reverses the process. It maps the generic placeholders back to your original variable and function names, integrating the AI's suggestions directly into your code's context.

> **The Result:** You get the full power of world-class AI models without ever exposing your sensitive source code to them. This is the core value of 0Pirate.

## Supported Cloud Providers

These providers offer powerful, managed AI models accessible via API keys. You can add and securely manage your own keys in the **Account > API Keys** section of the application.

### OpenAI
- **gpt-4o-mini**: A fast, affordable, and highly capable multimodal model. Excellent for a wide range of tasks including code generation, conversation, and analysis.
- **gpt-4o**: OpenAI's most advanced model, offering state-of-the-art performance, intelligence, and multimodal capabilities. Ideal for complex reasoning and nuanced code understanding.

### Anthropic
- **claude-3-haiku**: Anthropic's fastest and most compact model, designed for near-instant responsiveness. Great for straightforward tasks and quick code reviews.
- **claude-3.5-sonnet**: The latest model in the Sonnet family, offering a balance of high intelligence and speed. It excels at complex instruction following and code generation.

### Google Gemini
- **gemini-1.5-flash**: A lightweight, fast, and cost-efficient multimodal model optimized for high-volume tasks.
- **gemini-1.5-pro**: Google's state-of-the-art foundation model, featuring a massive 1 million token context window and advanced multimodal reasoning. Perfect for analyzing entire codebases.
- **gemini-2.5-flash & pro**: The next generation of Gemini models, offering enhanced performance and efficiency (when available).

### Mistral AI
- **mistral-large-latest**: Mistral's flagship model, offering top-tier reasoning capabilities and high performance on benchmarks. A powerful alternative for complex tasks.

### Groq
- **llama-3.1-8b-instant & 70b-versatile**: Access open-source Llama 3.1 models running on Groq's custom LPU hardware, providing unparalleled inference speed. Ideal for real-time applications.

### Deepseek
- **deepseek-chat**: A powerful chat-based model with strong general reasoning and conversational abilities.

## Local Models via Ollama

For maximum privacy and control, you can run open-source models directly on your own machine using Ollama. Our application can connect to your local Ollama instance.

### Recommended Models
- **llama3:latest**: Meta's latest generation of Llama. A powerful, general-purpose model that excels at coding and instruction following. A great starting point.
- **codegemma:latest**: A family of lightweight, state-of-the-art open models from Google, fine-tuned specifically for code-related tasks.
- **mistral:latest**: The base Mistral 7B model. It is highly efficient and performs well on a wide range of tasks.
- **qwen2.5-coder:7b-instruct**: A powerful coding model from Alibaba Cloud, specifically fine-tuned for code generation and understanding.

### Setup Instructions
To connect to your local Ollama server, please refer to the "Setup" guide that appears in the application when you select **ollama** as the provider. This guide provides the necessary commands to configure your server correctly.
`;
