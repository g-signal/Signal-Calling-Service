#!/bin/bash
# build-calling-service.sh - Build script for Signal Calling Service components

set -e  # Exit on any error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_component() {
    echo -e "${BLUE}[COMPONENT]${NC} $1"
}

# Configuration
CONFIG_FILE="config/build.properties"
DEFAULT_DOCKER_REPO=""
DEFAULT_TAG=""



# Function to read property from config file
read_property() {
    local key="$1"
    local config_file="$2"
    grep "^${key}=" "$config_file" 2>/dev/null | cut -d'=' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Read configuration
print_status "Reading configuration from $CONFIG_FILE..."
DOCKER_REPO=$(read_property "docker.repo" "$CONFIG_FILE")
BUILD_PUSH=$(read_property "build.push" "$CONFIG_FILE")
BUILD_LATEST_TAG=$(read_property "build.latest_tag" "$CONFIG_FILE")
BUILD_OPTIMIZATION=$(read_property "build.optimization" "$CONFIG_FILE")
BUILD_BOOTSTRAP=$(read_property "build.bootstrap" "$CONFIG_FILE")
BUILD_FRONTEND=$(read_property "build.frontend" "$CONFIG_FILE")
BUILD_BACKEND=$(read_property "build.backend" "$CONFIG_FILE")

# Set defaults
DOCKER_REPO=${DOCKER_REPO:-$DEFAULT_DOCKER_REPO}
BUILD_PUSH=${BUILD_PUSH:-"true"}
BUILD_LATEST_TAG=${BUILD_LATEST_TAG:-"true"}
BUILD_OPTIMIZATION=${BUILD_OPTIMIZATION:-"skylake"}
BUILD_BOOTSTRAP=${BUILD_BOOTSTRAP:-"true"}
BUILD_FRONTEND=${BUILD_FRONTEND:-"true"}
BUILD_BACKEND=${BUILD_BACKEND:-"true"}

# Extract version information
print_status "Extracting version information..."
VERSION=$(grep '^version =' Cargo.toml | head -1 | cut -d'"' -f2 || echo "dev-$(date +%Y%m%d%H%M%S)")
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
FULL_VERSION="${VERSION}-${GIT_COMMIT}"

print_status "Build Information:"
echo "  Version: $VERSION"
echo "  Git Commit: $GIT_COMMIT"
echo "  Full Version: $FULL_VERSION"
echo "  Docker Repo: $DOCKER_REPO"
echo "  Optimization: $BUILD_OPTIMIZATION"
echo "  Components to build:"
[[ "$BUILD_BOOTSTRAP" == "true" ]] && echo "    - Bootstrap"
[[ "$BUILD_FRONTEND" == "true" ]] && echo "    - Frontend"
[[ "$BUILD_BACKEND" == "true" ]] && echo "    - Backend"

# Build function for each component
build_component() {
    local component="$1"
    local dockerfile_path="$2"
    local context_path="$3"
    local image_name="${DOCKER_REPO}/signal-calling-${component}"

    print_component "Building $component component..."

    # Build arguments (matching docker-compose.yml format)
    local build_args=""
    if [[ "$component" == "frontend" || "$component" == "backend" ]]; then
        build_args="--build-arg rust_flags=-Ctarget-cpu=${BUILD_OPTIMIZATION}"
    fi

    print_status "Building with optimization: -Ctarget-cpu=${BUILD_OPTIMIZATION}"

    # Build Docker image (using same pattern as docker-compose.yml)
    docker build \
        $build_args \
        --file "$dockerfile_path" \
        --tag "$image_name:$VERSION" \
        --tag "$image_name:$FULL_VERSION" \
        "$context_path"

    # Add latest tag if configured
    if [[ "$BUILD_LATEST_TAG" == "true" ]]; then
        docker tag "$image_name:$VERSION" "$image_name:latest"
        print_status "Tagged $component as latest"
    fi

    print_status "$component build completed successfully!"

    # Push to registry if configured
    if [[ "$BUILD_PUSH" == "true" ]]; then
        print_status "Pushing $component images to registry..."

        docker push "$image_name:$VERSION"
        docker push "$image_name:$FULL_VERSION"

        if [[ "$BUILD_LATEST_TAG" == "true" ]]; then
            docker push "$image_name:latest"
        fi

        print_status "$component images pushed successfully!"
    fi
}

# Build components based on configuration
if [[ "$BUILD_BOOTSTRAP" == "true" ]]; then
    build_component "bootstrap" "docker/bootstrap/Dockerfile" "docker/bootstrap"
fi

if [[ "$BUILD_FRONTEND" == "true" ]]; then
    build_component "frontend" "frontend/Dockerfile" "."
fi

if [[ "$BUILD_BACKEND" == "true" ]]; then
    build_component "backend" "backend/Dockerfile" "."
fi

# Generate docker-compose override file for built images
print_status "Generating docker-compose override file..."
cat > docker-compose.override.yml << EOF
# Auto-generated override file for custom built images
# Generated on $(date)

services:
EOF

if [[ "$BUILD_BOOTSTRAP" == "true" ]]; then
cat >> docker-compose.override.yml << EOF
  bootstrap:
    image: ${DOCKER_REPO}/signal-calling-bootstrap:${VERSION}
EOF
fi

if [[ "$BUILD_FRONTEND" == "true" ]]; then
cat >> docker-compose.override.yml << EOF
  calling_frontend:
    image: ${DOCKER_REPO}/signal-calling-frontend:${VERSION}
EOF
fi

if [[ "$BUILD_BACKEND" == "true" ]]; then
cat >> docker-compose.override.yml << EOF
  calling_backend:
    image: ${DOCKER_REPO}/signal-calling-backend:${VERSION}
EOF
fi

print_status "Build Summary:"
echo "  Built images:"
[[ "$BUILD_BOOTSTRAP" == "true" ]] && echo "    - ${DOCKER_REPO}/signal-calling-bootstrap:${VERSION}"
[[ "$BUILD_FRONTEND" == "true" ]] && echo "    - ${DOCKER_REPO}/signal-calling-frontend:${VERSION}"
[[ "$BUILD_BACKEND" == "true" ]] && echo "    - ${DOCKER_REPO}/signal-calling-backend:${VERSION}"

if [[ "$BUILD_PUSH" == "true" ]]; then
    echo "  All images pushed to registry successfully!"
else
    echo "  Images built locally (push disabled)"
fi

echo ""
print_status "To use the built images:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.override.yml up"

print_status "Script completed successfully!"