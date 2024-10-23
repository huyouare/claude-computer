# claude-computer

## Warnings

This is a modified fork of https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo, but operating with a VM. Please use caution:

> [!CAUTION]
> Computer use is a beta feature. Please be aware that computer use poses unique risks that are distinct from standard API features or chat interfaces. These risks are heightened when using computer use to interact with the internet. To minimize risks, consider taking precautions such as:
>
> 1. Use a dedicated virtual machine or container with minimal privileges to prevent direct system attacks or accidents.
> 2. Avoid giving the model access to sensitive data, such as account login information, to prevent information theft.
> 3. Limit internet access to an allowlist of domains to reduce exposure to malicious content.
> 4. Ask a human to confirm decisions that may result in meaningful real-world consequences as well as any tasks requiring affirmative consent, such as accepting cookies, executing financial transactions, or agreeing to terms of service.
>
> In some circumstances, Claude will follow commands found in content even if it conflicts with the user's instructions. For example, instructions on webpages or contained in images may override user instructions or cause Claude to make mistakes. We suggest taking precautions to isolate Claude from sensitive data and actions to avoid risks related to prompt injection.
>
> Finally, please inform end users of relevant risks and obtain their consent prior to enabling computer use in your own products.

> [!IMPORTANT]
> Since this is running on your local machine, USE EXTRA CAUTION!!!

## Development Setup

### Pre-Installation

Currently, this only works with lower screen resolution. Try something like 1280x720 for best results.

You will also need to give permissions to your terminal (such as iTerm) to take screenshots and use accessibility.

### Installation

1. Install Poetry: https://python-poetry.org/docs/#installation
2. Install dependencies: `poetry install --no-root`
3. Activate the virtual environment: `poetry shell`
4. Run the application: `streamlit run streamlit.py`
