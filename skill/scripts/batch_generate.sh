#!/bin/bash
# Batch Synset Generator
# Generates synsets continuously or in batches

set -e

SYNSETS_DIR="/home/ubt18/synsets"
WORKFLOW_SCRIPT="$SYNSETS_DIR/skill/workflows/generate_synset.py"
LOG_FILE="$SYNSETS_DIR/logs/generation.log"

# Create logs directory
mkdir -p "$SYNSETS_DIR/logs"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to get count of existing synsets
count_existing() {
    if [ -d "$SYNSETS_DIR/data/synsets" ]; then
        ls -1 "$SYNSETS_DIR/data/synsets" | grep -c "^ili_" || echo "0"
    else
        echo "0"
    fi
}

# Main generation loop
generate_batch() {
    local batch_size=${1:-10}
    local target=${2:-117480}
    
    log "Starting batch generation: batch_size=$batch_size, target=$target"
    
    while true; do
        local current=$(count_existing)
        local remaining=$((target - current))
        
        if [ "$remaining" -le 0 ]; then
            log "Target reached! Generated $current synsets."
            break
        fi
        
        local to_generate=$batch_size
        if [ "$remaining" -lt "$batch_size" ]; then
            to_generate=$remaining
        fi
        
        log "Progress: $current/$target ($remaining remaining). Generating $to_generate..."
        
        # Generate batch
        for i in $(seq 1 $to_generate); do
            if python3 "$WORKFLOW_SCRIPT" 2>&1 >> "$LOG_FILE"; then
                log "  ✓ Generated synset $i/$to_generate"
            else
                log "  ✗ Failed on synset $i/$to_generate, continuing..."
            fi
            sleep 2  # Brief pause between synsets
        done
        
        log "Batch complete. Current count: $(count_existing)"
        sleep 5  # Pause between batches
    done
}

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Generate synset data at scale using Hermes Agent.

OPTIONS:
    -b, --batch SIZE     Number of synsets per batch (default: 10)
    -t, --target NUM     Target total synsets (default: 117480)
    -c, --continuous     Run continuously until target reached
    -o, --once           Generate one synset and exit
    -h, --help           Show this help

EXAMPLES:
    $0 --once                    # Generate one synset
    $0 --batch 5                 # Generate 5 synsets
    $0 --batch 10 --continuous   # Generate 10 at a time, continuously
    $0 --target 1000 --batch 50  # Generate until 1000 synsets exist

EOF
}

# Parse arguments
BATCH_SIZE=10
TARGET=117480
MODE="batch"

while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--batch)
            BATCH_SIZE="$2"
            shift 2
            ;;
        -t|--target)
            TARGET="$2"
            shift 2
            ;;
        -c|--continuous)
            MODE="continuous"
            shift
            ;;
        -o|--once)
            MODE="once"
            BATCH_SIZE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run based on mode
case $MODE in
    once)
        log "Generating one synset..."
        python3 "$WORKFLOW_SCRIPT"
        ;;
    batch|continuous)
        generate_batch "$BATCH_SIZE" "$TARGET"
        ;;
esac

log "Done!"
