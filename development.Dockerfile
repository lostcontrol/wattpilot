FROM python:3.8

# Create a non-root user.
ARG USERNAME=me
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# See https://github.com/moby/moby/issues/5419 to understand why we need to call
# useradd with "-l". Otherwise, docker will create huge files inside the container.
RUN groupadd --gid $USER_GID $USERNAME && \
    useradd -l --uid $USER_UID --gid $USER_GID -m $USERNAME && \
    mkdir -p /home/$USERNAME/.vscode-server /home/$USERNAME/.vscode-server-insiders && \
    chown ${USER_UID}:${USER_GID} /home/$USERNAME/.vscode-server*

WORKDIR /code
COPY requirements*.txt /code/
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . /code/

USER $USERNAME
ENV HOME=/home/$USERNAME

