#!/bin/bash
# filepath: monitor_python_cpu.sh

# Default refresh interval in seconds
INTERVAL=2
TOP_N=""
LOG_FILE=""

print_usage() {
    echo "Usage: $0 [-i INTERVAL] [-n TOP_N] [-l LOG_FILE]"
    echo "  -i INTERVAL    Refresh interval in seconds (default: 2)"
    echo "  -n TOP_N       Show only top N processes by CPU usage"
    echo "  -l LOG_FILE    Log results to specified file"
    echo "  -h             Display this help message"
    exit 1
}

# Parse command line arguments
while getopts "i:n:l:h" opt; do
    case ${opt} in
        i )
            INTERVAL=$OPTARG
            ;;
        n )
            TOP_N=$OPTARG
            ;;
        l )
            LOG_FILE=$OPTARG
            ;;
        h )
            print_usage
            ;;
        \? )
            print_usage
            ;;
    esac
done

# Check if ps command exists
if ! command -v ps &> /dev/null; then
    echo "Error: ps command not found. Please install procps package."
    exit 1
fi

monitor() {
    trap "echo -e '\nMonitoring stopped.'; exit 0" INT

    while true; do
        # Clear the screen
        clear
        
        # Print header with timestamp
        DATE=$(date "+%Y-%m-%d %H:%M:%S")
        echo "Python Process CPU Monitor - $DATE"
        echo "Refresh interval: ${INTERVAL}s"
        echo "Press Ctrl+C to exit"
        echo "----------------------------------------"
        
        # Get total CPU and memory usage
        TOTAL_CPU=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
        TOTAL_MEM=$(free | grep Mem | awk '{print $3/$2 * 100}')
        printf "Total CPU Usage: %.1f%%\n" "$TOTAL_CPU"
        printf "Total Memory Usage: %.1f%%\n" "$TOTAL_MEM"
        echo ""
        
        # Get Python processes with CPU and memory usage
        # Format: PID USER CPU% MEM% VSZ RSS TTY STAT START TIME COMMAND
        HEADER="PID   CPU%   MEM%   COMMAND"
        echo "$HEADER"
        echo "----------------------------------------"
        
        if [ -n "$TOP_N" ]; then
            # Show only top N processes
            PROCESS_DATA=$(ps -eo pid,pcpu,pmem,command --sort=-pcpu | grep -E 'python|python3' | grep -v grep | head -n "$TOP_N")
        else
            # Show all Python processes
            PROCESS_DATA=$(ps -eo pid,pcpu,pmem,command --sort=-pcpu | grep -E 'python|python3' | grep -v grep)
        fi
        
        if [ -z "$PROCESS_DATA" ]; then
            echo "No Python processes found."
        else
            # Format and display the data
            echo "$PROCESS_DATA" | awk '{printf "%-6s %-6.1f %-6.1f %s\n", $1, $2, $3, $4" "$5" "$6" "$7" "$8" "$9" "$10}'
            
            # Log to file if specified
            if [ -n "$LOG_FILE" ]; then
                echo "--- $DATE ---" >> "$LOG_FILE"
                echo "$HEADER" >> "$LOG_FILE"
                echo "$PROCESS_DATA" | awk '{printf "%-6s %-6.1f %-6.1f %s\n", $1, $2, $3, $4" "$5" "$6" "$7" "$8" "$9" "$10}' >> "$LOG_FILE"
                echo "" >> "$LOG_FILE"
            fi
        fi
        
        # Wait for the specified interval
        sleep "$INTERVAL"
    done
}

# Start monitoring
monitor