#!/bin/bash

KEPLOY_TELEMETRY_URL="https://telemetry.keploy.io/analytics"

keploy_resolve_installation_id() {
    [ -n "$INSTALLATION_ID" ] && return 0
    local id_file="$HOME/.keploy/installation_id"
    if [ -f "$id_file" ]; then
        INSTALLATION_ID=$(cat "$id_file" 2>/dev/null)
    fi
    if [ -z "$INSTALLATION_ID" ]; then
        mkdir -p "$HOME/.keploy" 2>/dev/null
        INSTALLATION_ID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null \
            || uuidgen 2>/dev/null \
            || python3 -c 'import uuid;print(uuid.uuid4())' 2>/dev/null)
        [ -n "$INSTALLATION_ID" ] && echo "$INSTALLATION_ID" > "$id_file" 2>/dev/null
    fi
}

keploy_detect_ci() {
    KEPLOY_IS_CI=false
    KEPLOY_CI_PROVIDER=""
    if   [ "$GITHUB_ACTIONS" = "true" ];      then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="github_actions"
    elif [ "$GITLAB_CI" = "true" ];           then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="gitlab_ci"
    elif [ "$CIRCLECI" = "true" ];            then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="circleci"
    elif [ "$TRAVIS" = "true" ];              then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="travis"
    elif [ "$BUILDKITE" = "true" ];           then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="buildkite"
    elif [ "$DRONE" = "true" ];               then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="drone"
    elif [ "$APPVEYOR" = "true" ];            then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="appveyor"
    elif [ -n "$JENKINS_URL" ];               then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="jenkins"
    elif [ -n "$TEAMCITY_VERSION" ];          then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="teamcity"
    elif [ -n "$BITBUCKET_BUILD_NUMBER" ];    then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="bitbucket"
    elif [ -n "$CODEBUILD_BUILD_ID" ];        then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="aws_codebuild"
    elif [ "${CI:-}" = "true" ];              then KEPLOY_IS_CI=true; KEPLOY_CI_PROVIDER="unknown"
    fi
    if [ "$IS_CI" = true ] && [ "$KEPLOY_IS_CI" = false ]; then
        KEPLOY_IS_CI=true
        KEPLOY_CI_PROVIDER="flag"
    fi
}

keploy_detect_installed_version() {
    local binary="$1"
    local out
    out=$("$binary" -v 2>/dev/null) || out=$("$binary" --version 2>/dev/null) || return 0
    echo "$out" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*' | tail -n 1
}

keploy_send_install_event() {
    local stage="$1"
    local variant="$2"
    local v="${3:-}"
    local no_root_val="${NO_ROOT:-false}"
    keploy_resolve_installation_id
    keploy_detect_ci
    local os_str arch_str created_at
    os_str=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch_str=$(uname -m)
    created_at=$(date +%s)
    local payload
    payload="{\"eventType\":\"InstallScript\",\"createdAt\":${created_at},\"installationId\":\"${INSTALLATION_ID}\",\"os\":\"${os_str}\",\"arch\":\"${arch_str}\",\"keploy_version\":\"${v}\",\"is_ci\":${KEPLOY_IS_CI},\"ci_provider\":\"${KEPLOY_CI_PROVIDER}\",\"meta\":{\"stage\":\"${stage}\",\"variant\":\"${variant}\",\"no_root\":${no_root_val}}}"
    curl -fsS --max-time 3 -X POST "$KEPLOY_TELEMETRY_URL" \
        -H 'content-type: application/json; charset=utf-8' \
        -d "$payload" >/dev/null 2>&1 || true
}

installAgent() {
    # Global variables for Agent installation
    version="latest"
    os_name=""
    arch_name=""
    install_dir="$HOME/.keploy-agent/bin"
    binary_name="keploy-agent"
    shell_profile=""
    tmp_dir=""
    asset_filename=""
    download_url=""

    # Functions copied from keploy-agent.sh
    check_dependencies() {
        if ! command -v curl &> /dev/null; then
            echo "Error: 'curl' is required but not installed." >&2
            echo "Please install curl using your package manager (e.g., 'sudo apt install curl' on Ubuntu, 'brew install curl' on macOS)." >&2
            return 1
        fi

        if ! command -v unzip &> /dev/null; then
            echo "Error: 'unzip' is required but not installed." >&2
            echo "Please install unzip using your package manager (e.g., 'sudo apt install unzip' on Ubuntu, 'brew install unzip' on macOS)." >&2
            return 1
        fi
    }

    parse_arguments() {
        while [ "$#" -gt 0 ]; do
            case "$1" in
                -v)
                    if [[ "$2" =~ ^v[0-9]+\.[0-9]+\.[0-9]+-agent.* ]]; then
                        version="$2"
                        shift 2
                    else
                        echo "Error: Invalid version format." >&2
                        echo "Please use a semantic version format prefixed with 'v', like '-v v1.2.3-agent'." >&2
                        return 1
                    fi
                    ;;
                *)
                    echo "Warning: Ignoring unknown argument: $1" >&2
                    shift 1
                    ;;
            esac
        done
    }

    detect_os_arch() {
        case "$(uname -m)" in
            x86_64)
                arch_name="amd64"
                ;;
            aarch64|arm64)
                arch_name="arm64"
                ;;
            *)
                echo "Error: Unsupported architecture: $(uname -m)" >&2
                return 1
                ;;
        esac

        case "$(uname -s)" in
            Linux)
                os_name="linux"
                ;;
            Darwin)
                os_name="darwin_all"
                arch_name=""
                ;;
            *)
                echo "Error: Unsupported operating system: $(uname -s)" >&2
                return 1
                ;;
        esac
    }

    construct_download_url() {
        asset_filename="${binary_name}-${os_name}"
        if [ -n "$arch_name" ]; then
            asset_filename="${asset_filename}_${arch_name}"
        fi
        asset_filename="${asset_filename}.zip"

        if [ "$version" = "latest" ]; then
            download_url="https://keploy.io/ent/dl/latest/${asset_filename}"
        else
            download_url="https://keploy.io/ent/dl/${version}/${asset_filename}"
        fi
    }

    download_and_extract() {
        local zip_file="${tmp_dir}/${asset_filename}"
        curl --progress-bar --show-error --location --output "$zip_file" "$download_url"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to download the Keploy Agent." >&2
            echo "Please check the version number and your network connection." >&2
            return 1
        fi

        unzip -o "$zip_file" -d "$tmp_dir" > /dev/null
        if [ $? -ne 0 ]; then
            echo "Error: Failed to unzip the archive." >&2
            return 1
        fi

        local binary_path="${tmp_dir}/${binary_name}"
        if [ ! -f "$binary_path" ]; then
            echo "Error: Binary not found in the archive." >&2
            return 1
        fi

        echo "$binary_path"
    }

    install_binary() {
        local binary_path="$1"
        local install_path="${install_dir}/${binary_name}"

        echo "Installing Keploy Agent to: $install_dir"
        mkdir -p "$install_dir"
        if [ ! -d "$install_dir" ]; then
            echo "Error: Failed to create installation directory: $install_dir" >&2
            return 1
        fi

        mv "$binary_path" "$install_path"
        if [ $? -ne 0 ]; then
            echo "Error: Failed to move the binary to the installation directory." >&2
            return 1
        fi

        chmod +x "$install_path"
    }

    update_shell_profile() {
        local path_export_cmd="export PATH=\"${install_dir}:\$PATH\""
        local current_shell
        current_shell=$(basename "$SHELL")

        if [[ "$current_shell" = "zsh" || "$current_shell" = "-zsh" ]]; then
            shell_profile="$HOME/.zshrc"
        elif [[ "$current_shell" = "bash" || "$current_shell" = "-bash" ]]; then
            if [ -f "$HOME/.bash_profile" ]; then
                shell_profile="$HOME/.bash_profile"
            else
                shell_profile="$HOME/.bashrc"
            fi
        else
            shell_profile="$HOME/.profile"
        fi

        echo "Updating your shell profile: $shell_profile"

        if ! grep -q "# --- Keploy Agent ---" "$shell_profile"; then
            [ -n "$(tail -c 1 "$shell_profile")" ] && echo >> "$shell_profile"
            echo "" >> "$shell_profile"
            echo "# --- Keploy Agent ---" >> "$shell_profile"
            echo "$path_export_cmd" >> "$shell_profile"
        fi
    }

    print_instructions() {
        echo ""
        echo "✅ Keploy Agent installed successfully!"
        echo ""
        echo "To get started, please restart your terminal or run the following command:"
        echo "   source \"$shell_profile\""
        echo ""
        echo "You can then verify the installation by running:"
        echo "   keploy-agent --help"
        echo ""
    }

    tmp_dir=$(mktemp -d)
    trap "rm -rf \"${tmp_dir}\"" EXIT

    check_dependencies || return 1
    parse_arguments "$@" || return 1
    detect_os_arch || return 1
    construct_download_url
    keploy_send_install_event start agent ""
    if [ "$version" = "latest" ]; then
        echo "Installing the latest version of Keploy Agent..."
    else
        echo "Installing Keploy Agent version: $version..."
    fi
    echo "Downloading from: ${download_url}"

    local binary_path
    binary_path=$(download_and_extract)
    if [ $? -ne 0 ]; then
        return 1
    fi

    install_binary "$binary_path" || return 1
    update_shell_profile || return 1
    print_instructions
}

installKeploy() {
    version="latest"
    IS_CI=false
    NO_ROOT=false
    PLATFORM="$(basename "$SHELL")"
    for arg in "$@"; do
        case $arg in
        -isCI)
            IS_CI=true
            shift
            ;;
        -v)
            shift
            if [[ "$1" =~ ^v[0-9]+.* ]]; then
                version="${1:1}"
                shift
            else
                echo "Invalid version format. Please use '-v v<semver>'."
                return 1
            fi
            ;;
        -noRoot)
            NO_ROOT=true
            shift
            ;;
        *) ;;
        esac
    done

    if [ "$version" != "latest" ]; then
        echo "Installing Keploy version: $version......"
    fi

    keploy_send_install_event start enterprise ""

    install_keploy_arm() {
        if [ "$version" != "latest" ]; then
            download_url="https://keploy.io/ent/dl/$version/enterprise_linux_arm64"
        else
            download_url="https://keploy.io/ent/dl/latest/enterprise_linux_arm64"
        fi
        curl --progress-bar --location "$download_url" -o /tmp/keploy

        if [ "$NO_ROOT" = true ]; then
            chmod a+x /tmp/keploy && mkdir -p "$HOME/.keploy/bin" && mv /tmp/keploy "$HOME/.keploy/bin"
        else
            sudo chmod a+x /tmp/keploy && sudo mkdir -p /usr/local/bin && sudo mv /tmp/keploy /usr/local/bin
        fi

        # Only set sudo alias for v2.x.x versions
        if [[ "$version" =~ ^2\.[0-9]+\.[0-9]+ ]]; then
            set_alias 'sudo -E env PATH="$PATH" keploy'
        elif [ "$NO_ROOT" = true ]; then
            # For v3 with -noRoot, just update PATH (no sudo alias needed)
            if [[ "$PLATFORM" = "zsh" || "$PLATFORM" = "-zsh" ]]; then
                update_path "$HOME/.zshrc"
            elif [[ "$PLATFORM" = "bash" || "$PLATFORM" = "-bash" ]]; then
                update_path "$HOME/.bashrc"
            else
                update_path "$HOME/.profile"
            fi
        fi

        check_docker_status_for_linux
        dockerStatus=$?
        if [ "$dockerStatus" -eq 0 ]; then
            return
        fi
        add_network
    }

    install_keploy_amd() {
        if [ $version != "latest" ]; then
            download_url="https://keploy.io/ent/dl/$version/enterprise_linux_amd64"
        else
            download_url="https://keploy.io/ent/dl/latest/enterprise_linux_amd64"
        fi
        curl --progress-bar --location "$download_url" -o /tmp/keploy

        if [ "$NO_ROOT" = true ]; then
            chmod a+x /tmp/keploy && mkdir -p "$HOME/.keploy/bin" && mv /tmp/keploy "$HOME/.keploy/bin"
        else
            sudo chmod a+x /tmp/keploy && sudo mkdir -p /usr/local/bin && sudo mv /tmp/keploy /usr/local/bin
        fi

        # Only set sudo alias for v2.x.x versions
        if [[ "$version" =~ ^2\.[0-9]+\.[0-9]+ ]]; then
            set_alias 'sudo -E env PATH="$PATH" keploy'
        elif [ "$NO_ROOT" = true ]; then
            # For v3 with -noRoot, just update PATH (no sudo alias needed)
            if [[ "$PLATFORM" = "zsh" || "$PLATFORM" = "-zsh" ]]; then
                update_path "$HOME/.zshrc"
            elif [[ "$PLATFORM" = "bash" || "$PLATFORM" = "-bash" ]]; then
                update_path "$HOME/.bashrc"
            else
                update_path "$HOME/.profile"
            fi
        fi

        check_docker_status_for_linux
        dockerStatus=$?
        if [ "$dockerStatus" -eq 0 ]; then
            return
        fi
        add_network
    }

    append_to_rc() {
        last_byte=$(tail -c 1 $2)
        if [[ "$last_byte" != "" ]]; then
            echo -e "\n$1" >>$2
        else
            echo "$1" >>$2
        fi
        source $2
    }

    update_path() {
        PATH_CMD="export PATH=\"\$HOME/.keploy/bin:\$PATH\""
        rc_file="$1"
        if [ -f "$rc_file" ]; then
            if ! grep -q "$PATH_CMD" "$rc_file"; then
                append_to_rc "$PATH_CMD" "$rc_file"
            fi
        fi
        # Always export PATH for the current session
        export PATH="$HOME/.keploy/bin:$PATH"
    }

    # Get the alias to set and set it
    set_alias() {
        current_shell="$PLATFORM"
        if [ "$NO_ROOT" = "true" ]; then
            # Just update the PATH in .zshrc or .bashrc, no alias needed
            if [[ "$current_shell" = "zsh" || "$current_shell" = "-zsh" ]]; then
                update_path "$HOME/.zshrc"
            elif [[ "$current_shell" = "bash" || "$current_shell" = "-bash" ]]; then
                update_path "$HOME/.bashrc"
            else
                update_path "$HOME/.profile"
            fi
            return
        fi

        # Check if the command is for docker or not
        if [[ "$1" == *"docker"* ]]; then
            # Check if the user is a member of the docker group
            check_sudo
            sudoCheck=$?
            if [ "$sudoCheck" -eq 0 ] && [ "$OS_NAME" = "Linux" ]; then
                # Add sudo to the alias.
                ALIAS_CMD="alias keploy='sudo $1'"
            else
                ALIAS_CMD="alias keploy='$1'"
            fi
        else
            ALIAS_CMD="alias keploy='$1'"
        fi
        
        # Apply the alias to shell config
        current_shell="$(basename "$SHELL")"
        if [[ "$current_shell" = "zsh" || "$current_shell" = "-zsh" ]]; then
            if [ -f ~/.zshrc ]; then
                if grep -q "alias keploy=" ~/.zshrc; then
                    if [ "$OS_NAME" = "Darwin" ]; then
                        sed -i '' '/alias keploy/d' ~/.zshrc
                    else
                        sed -i '/alias keploy/d' ~/.zshrc
                    fi
                fi
                append_to_rc "$ALIAS_CMD" ~/.zshrc
            else
                alias keploy="$1"
            fi
        elif [[ "$current_shell" = "bash" || "$current_shell" = "-bash" ]]; then
            if [ -f ~/.bashrc ]; then
                if grep -q "alias keploy=" ~/.bashrc; then
                    if [ "$OS_NAME" = "Darwin" ]; then
                        sed -i '' '/alias keploy/d' ~/.bashrc
                    else
                        sed -i '/alias keploy/d' ~/.bashrc
                    fi
                fi
                append_to_rc "$ALIAS_CMD" ~/.bashrc
            else
                alias keploy="$1"
            fi
        else
            alias keploy="$1"
        fi
    }

    check_sudo() {
        if groups | grep -q '\bdocker\b'; then
            return 1
        else
            return 0
        fi
    }

    check_docker_status_for_linux() {
        check_sudo
        sudoCheck=$?
        network_alias=""
        if [ "$sudoCheck" -eq 0 ]; then
            # Add sudo to docker
            network_alias="sudo"
        fi
        if ! $network_alias which docker &>/dev/null; then
            echo -n "Docker not found on device, please install docker and reinstall keploy if you have applications running on docker"
            return 0
        fi
        if ! $network_alias docker info &>/dev/null; then
            echo "Please start Docker and reinstall keploy if you have applications running on docker"
            return 0
        fi
        return 1
    }

    check_docker_status_for_Darwin() {
        check_sudo
        sudoCheck=$?
        network_alias=""
        if [ "$sudoCheck" -eq 0 ]; then
            # Add sudo to docker
            network_alias="sudo"
        fi
        if ! $network_alias which docker &>/dev/null; then
            echo -n "Docker not found on device, please install docker to use Keploy"
            return 0
        fi
        # Check if docker is running
        if ! $network_alias docker info &>/dev/null; then
            echo "Keploy only supports intercepting and replaying docker containers on macOS, and requires Docker to be installed and running. Please start Docker and try again."
            return 0
        fi
        return 1
    }

    add_network() {
        if ! $network_alias docker network ls | grep -q 'keploy-network'; then
            $network_alias docker network create keploy-network
        fi
    }

    delete_keploy_alias() {
        current_shell="$PLATFORM"
        shell_rc_file=""
        if [[ "$current_shell" = "zsh" || "$current_shell" = "-zsh" ]]; then
            shell_rc_file="$HOME/.zshrc"
        elif [[ "$current_shell" = "bash" || "$current_shell" = "-bash" ]]; then
            shell_rc_file="$HOME/.bashrc"
        else
            echo "Unsupported shell: $current_shell"
            return
        fi
        if [ -f "$shell_rc_file" ]; then
            if grep -q "alias keploy=" "$shell_rc_file"; then
                if [[ "$(uname)" = "Darwin" ]]; then
                    sed -i '' '/alias keploy/d' "$shell_rc_file"
                else
                    sed -i '/alias keploy/d' "$shell_rc_file"
                fi
            fi
        fi
        if alias keploy &>/dev/null; then
            unalias keploy
        fi
    }

    install_keploy_darwin_all() {
        delete_keploy_alias
        if [ $version != "latest" ]; then
            download_url="https://keploy.io/ent/dl/$version/enterprise_darwin_all"
        else
            download_url="https://keploy.io/ent/dl/latest/enterprise_darwin_all"
        fi
        rm -rf /tmp/keploy
        mkdir -p /tmp/keploy
        curl --progress-bar --location "$download_url" -o /tmp/keploy/keploy

        if [ "$NO_ROOT" = "true" ]; then
            target_dir="$HOME/.keploy/bin"
            source_dir="/tmp/keploy/keploy"
            mkdir -p "$target_dir"
            if [ $? -ne 0 ]; then
                echo "Error: Failed to create directory $target_dir"
                exit 1
            fi

            if [ -f "$source_dir" ]; then
                mv "$source_dir" "$target_dir/keploy"
                if [ $? -ne 0 ]; then
                    echo "Error: Failed to move the keploy binary from $source_dir to $target_dir"
                    exit 1
                fi
            else
                echo "Error: $source_dir does not exist."
                exit 1
            fi

            chmod +x "$target_dir/keploy"
            if [ $? -ne 0 ]; then
                echo "Error: Failed to make the keploy binary executable"
                exit 1
            fi
        else
            source_dir="/tmp/keploy/keploy"
            sudo mkdir -p /usr/local/bin && sudo mv "$source_dir" /usr/local/bin/keploy
            sudo chmod +x /usr/local/bin/keploy
            if [ $? -ne 0 ]; then
                echo "Error: Failed to make the keploy binary executable"
                exit 1
            fi

            check_docker_status_for_Darwin
            dockerStatus=$?
            if [ "$dockerStatus" -eq 0 ]; then
                return
            fi

            add_network
        fi

        # Only set sudo alias for v2.x.x versions (macOS sets NO_ROOT=true, so this won't create alias)
        if [[ "$version" =~ ^2\.[0-9]+\.[0-9]+ ]]; then
            set_alias 'sudo -E env PATH="$PATH" keploy'
        elif [ "$NO_ROOT" = "true" ]; then
            # For v3 with -noRoot (macOS default), just update PATH (no sudo alias needed)
            if [[ "$PLATFORM" = "zsh" || "$PLATFORM" = "-zsh" ]]; then
                update_path "$HOME/.zshrc"
            elif [[ "$PLATFORM" = "bash" || "$PLATFORM" = "-bash" ]]; then
                update_path "$HOME/.bashrc"
            else
                update_path "$HOME/.profile"
            fi
        fi

    }

    install_docker() {
        if [ "$OS_NAME" = "Darwin" ]; then
            check_docker_status_for_Darwin
            dockerStatus=$?
            if [ "$dockerStatus" -eq 0 ]; then
                return
            fi
            add_network
            if ! docker volume inspect debugfs &>/dev/null; then
                docker volume create --driver local --opt type=debugfs --opt device=debugfs debugfs
            fi
            set_alias 'docker run --pull always --name keploy-v3 -p 16789:16789 --privileged --pid=host -it -v $(pwd):$(pwd) -w $(pwd) -v /sys/fs/cgroup:/sys/fs/cgroup -v debugfs:/sys/kernel/debug:rw -v /sys/fs/bpf:/sys/fs/bpf -v /var/run/docker.sock:/var/run/docker.sock -v '"$HOME"'/.keploy:/root/.keploy --rm docker.io/keploy/enterprise'
        else
            set_alias 'docker run --pull always --name keploy-v3 -p 16789:16789 --privileged --pid=host -it -v $(pwd):$(pwd) -w $(pwd) -v /sys/fs/cgroup:/sys/fs/cgroup -v /sys/kernel/debug:/sys/kernel/debug -v /sys/fs/bpf:/sys/fs/bpf -v /var/run/docker.sock:/var/run/docker.sock -v '"$HOME"'/.keploy:/root/.keploy --rm docker.io/keploy/enterprise'
        fi
    }

    ARCH=$(uname -m)

    OS_NAME="$(uname -s)"
    if [ "$OS_NAME" = "Darwin" ]; then
        NO_ROOT=true
    fi

    if [ "$IS_CI" = false ]; then
        if [ "$OS_NAME" = "Darwin" ]; then
            install_keploy_darwin_all
            return
        elif [ "$OS_NAME" = "Linux" ]; then
            if [ "$NO_ROOT" = false ]; then
                if ! mountpoint -q /sys/kernel/debug; then
                    sudo mount -t debugfs debugfs /sys/kernel/debug
                fi
            fi
            if [ "$ARCH" = "x86_64" ]; then
                install_keploy_amd
            elif [ "$ARCH" = "aarch64" ]; then
                install_keploy_arm
            else
                echo "Unsupported architecture: $ARCH"
                return
            fi
        elif [[ "$OS_NAME" == MINGW32_NT* ]] || [[ "$OS_NAME" == MINGW64_NT* ]]; then
            echo "\e]8;; https://pureinfotech.com/install-windows-subsystem-linux-2-windows-10\aWindows not supported please run on WSL2\e]8;;\a"
        else
            echo "Unknown OS, install Linux to run Keploy"
        fi
    else
        if [ "$ARCH" = "x86_64" ]; then
            install_keploy_amd
        elif [ "$ARCH" = "aarch64" ]; then
            install_keploy_arm
        else
            echo "Unsupported architecture: $ARCH"
            return
        fi
    fi
}

remove_scripts() {
    rm -rf keploy-enterprise.sh
    rm -rf install.sh
}

if [[ "$1" == "--agent" ]]; then
    installAgent "$@"
    if command -v keploy-agent &>/dev/null; then
        keploy-agent --help
        installed_version=$(keploy_detect_installed_version keploy-agent)
        keploy_send_install_event complete agent "$installed_version"
        remove_scripts
    fi
else
    installKeploy "$@"
    if command -v keploy &>/dev/null; then
        installed_version=$(keploy_detect_installed_version keploy)

        # CLI-flow (no-MCP path): drop the small Keploy skill into any
        # detected coding agent (~/.claude, ~/.cursor) so the log-driven
        # loop is discoverable from session one. Best-effort — the loop
        # works without it (every keploy command prints a NEXT block), so
        # never fail the install over a skill write.
        keploy skill install >/dev/null 2>&1 || true

        # Drop the previous `keploy example` invocation here. That
        # command dumps per-language `keploy record` / `keploy test`
        # usage blocks as the most prominent post-install content,
        # which surfaces the legacy manual record/replay CLI as the
        # primary "how to use Keploy" guide. The current primary
        # Keploy experience is the MCP-driven flow, set up via
        # `keploy mcp-install` after `keploy login`. Leading with
        # the legacy examples confused users into running the
        # record/test commands directly instead of going through
        # the MCP setup.
        #
        # `keploy --help` stays — its subcommand list keeps the CLI
        # surface discoverable for anyone scrolling the install output.
        # Cobra's Help template does append a small `Examples:` block
        # showing record/test usage, but it lands in the middle of the
        # scroll (above the Next-step box below). The Next-step box
        # is the last visible content; it lays out the `keploy login`
        # → `keploy mcp-install` walkthrough as numbered steps so the
        # reader's eye lands there on a fresh prompt.
        keploy --help 2>/dev/null || true

        cat <<EOF

╭──────────────────────────────────────────────────────────────────────────╮
│  ✓ Keploy installed (v${installed_version})
│
│  ▶ Next step:  keploy login  →  then  keploy mcp-install
│
│    1. keploy login         — browser OAuth (GitHub / Google / Microsoft).
│                              Unlocks cloud mock storage and dashboard
│                              reporting (free tier available).
│
│    2. keploy mcp-install   — wires Keploy's MCP server into your AI
│       --editor <name>        agent so you can author API tests
│       (or --all)             conversationally instead of running CLI
│                              commands by hand. The agent detects the
│                              service, generates chained-CRUD tests,
│                              proves they catch bugs via mutation,
│                              captures mocks for sandbox replay, and
│                              wires CI.
│
│                              Pick one form:
│                                keploy mcp-install --editor claude-code
│                                keploy mcp-install --editor cursor
│                                keploy mcp-install --editor github-copilot
│                                keploy mcp-install --editor windsurf
│                                keploy mcp-install --editor codex
│                                keploy mcp-install --editor antigravity
│                                keploy mcp-install --editor claude-desktop
│                                keploy mcp-install --all     (every detected agent in one shot)
│
│                              If you're an AI agent running this, pass
│                              --editor with YOUR own canonical name
│                              (e.g. Claude Code → claude-code; OpenAI
│                              Codex → codex; Google Antigravity →
│                              antigravity).
│                              keploy auto-fetches an MCP PAT and writes
│                              it inline into the agent's config — no
│                              manual env-var export needed.
│
│    Then ask your AI agent:  "generate Keploy API tests for this service."
│
│  ▶ No MCP?  Drive the loop straight from the CLI:
│       keploy status        — shows where you are + the next step (the
│                              "NEXT block"). Re-run it, follow what it
│                              says, repeat. Works in any terminal or AI
│                              agent, no MCP and no setup. The skill that
│                              teaches agents this loop was just installed
│                              into your detected agents.
╰──────────────────────────────────────────────────────────────────────────╯

EOF

        keploy_send_install_event complete enterprise "$installed_version"
        remove_scripts
    fi
fi
