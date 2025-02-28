#!/bin/bash
# filepath: monitor_python_cpu.sh

# Default refresh interval in seconds
INTERVAL=2
TOP_N=""
LOG_FILE=""

# ANSI color codes
BLUE="\e[1;34m"
GREEN="\e[1;32m"
YELLOW="\e[1;33m"
RED="\e[1;31m"
CYAN="\e[1;36m"
MAGENTA="\e[1;35m"
RESET="\e[0m"
BOLD="\e[1m"

# ANSI cursor and screen control
CLEAR_SCREEN="\e[2J"
HOME_POSITION="\e[H"
SAVE_CURSOR="\e[s"
RESTORE_CURSOR="\e[u"
CLEAR_LINE="\e[K"

print_usage() {
    echo -e "${BOLD}Usage: $0 [-i INTERVAL] [-n TOP_N] [-l LOG_FILE]${RESET}"
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

# Check if required commands exist
for cmd in ps top free; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd command not found. Please install the required packages.${RESET}"
        exit 1
    fi
done

# Function to draw a horizontal line
draw_line() {
    local width=$1
    printf "%${width}s\n" | tr " " "─"
}

# Function to get color based on percentage
get_color() {
    local percent=$1
    if (( $(echo "$percent < 30" | bc -l) )); then
        echo -ne "${GREEN}"
    elif (( $(echo "$percent < 70" | bc -l) )); then
        echo -ne "${YELLOW}"
    else
        echo -ne "${RED}"
    fi
}

# Function to go to a specific line
goto_line() {
    echo -ne "\e[${1};0H"
}

# Function to initialize the screen layout once
initialize_screen() {
    # Clear the screen and go to home position
    echo -ne "${CLEAR_SCREEN}${HOME_POSITION}"
    
    # Get terminal width
    TERM_WIDTH=$(tput cols)
    if [ "$TERM_WIDTH" -gt 100 ]; then
        TERM_WIDTH=100
    fi
    
    # Draw the static parts of the UI (frame)
    echo -e "${BLUE}╔$(draw_line $((TERM_WIDTH-2)))╗${RESET}"
    echo -e "${BLUE}║${RESET} ${BOLD}Python Process CPU Monitor${RESET}$(printf "%$((TERM_WIDTH-27))s")${BLUE}║${RESET}"
    echo -e "${BLUE}║${RESET} Refresh interval: ${INTERVAL}s | Press Ctrl+C to exit$(printf "%$((TERM_WIDTH-47))s")${BLUE}║${RESET}"
    echo -e "${BLUE}╠$(draw_line $((TERM_WIDTH-2)))╣${RESET}"
    
    # System stats header (static)
    echo -e "${BLUE}║${RESET} ${BOLD}System Statistics:${RESET}$(printf "%$((TERM_WIDTH-19))s")${BLUE}║${RESET}"
    echo -e "${BLUE}║${RESET} CPU Usage:                | Memory Usage:              | Load Average:$(printf "%$((TERM_WIDTH-69))s")${BLUE}║${RESET}"
    echo -e "${BLUE}╠$(draw_line $((TERM_WIDTH-2)))╣${RESET}"
    
    # Python processes header (static)
    echo -e "${BLUE}║${RESET} ${BOLD}Python Processes:${RESET}$(printf "%$((TERM_WIDTH-19))s")${BLUE}║${RESET}"
    echo -e "${BLUE}╟$(draw_line $((TERM_WIDTH-2)))╢${RESET}"
    echo -e "${BLUE}║${RESET} ${BOLD}PID    CPU%   MEM%   Threads   CPU Time   Command${RESET}$(printf "%$((TERM_WIDTH-48))s")${BLUE}║${RESET}"
    echo -e "${BLUE}╟$(draw_line $((TERM_WIDTH-2)))╢${RESET}"
    
    # Save the position where data updates will begin
    PROCESSES_START_LINE=$((LINENO + 1))
    
    # Create space for process list (we'll update this area later)
    echo -e "${BLUE}║${RESET} Gathering data...$(printf "%$((TERM_WIDTH-19))s")${BLUE}║${RESET}"
    echo -e "${BLUE}╚$(draw_line $((TERM_WIDTH-2)))╝${RESET}"
    
    # Store the initial process display line
    FIRST_PROCESS_LINE=11
}

update_timestamp() {
    local date_str=$(date "+%Y-%m-%d %H:%M:%S")
    goto_line 2
    echo -ne "\e[27C${CYAN}$date_str${RESET}${CLEAR_LINE}"
}

update_system_stats() {
    # Get system stats
    local total_cpu=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    local total_mem=$(free | grep Mem | awk '{print $3/$2 * 100}')
    local load_avg=$(cat /proc/loadavg | awk '{print $1" "$2" "$3}')
    
    # Update stats line (line 6)
    goto_line 6
    echo -ne "\e[12C"
    echo -ne "$(get_color $total_cpu)${total_cpu}%${RESET}"
    echo -ne "\e[19C"
    echo -ne "$(get_color $total_mem)${total_mem}%${RESET}" 
    echo -ne "\e[18C${load_avg}${CLEAR_LINE}"
}

update_processes() {
    # Get number of CPU cores
    NUM_CORES=$(grep -c ^processor /proc/cpuinfo)
    
    # Get Python processes with CPU and memory usage
    if [ -n "$TOP_N" ]; then
        # Show only top N processes
        PROCESS_DATA=$(ps -eo pid,pcpu,pmem,command --sort=-pcpu | grep -E 'python|python3' | grep -v grep | head -n "$TOP_N")
    else
        # Show all Python processes
        PROCESS_DATA=$(ps -eo pid,pcpu,pmem,command --sort=-pcpu | grep -E 'python|python3' | grep -v grep)
    fi
    
    # Get terminal width for formatting
    TERM_WIDTH=$(tput cols)
    if [ "$TERM_WIDTH" -gt 100 ]; then
        TERM_WIDTH=100
    fi
    
    # Clear the process area by going to the first process line
    goto_line $FIRST_PROCESS_LINE
    
    if [ -z "$PROCESS_DATA" ]; then
        echo -e "${BLUE}║${RESET} ${YELLOW}No Python processes found.${RESET}$(printf "%$((TERM_WIDTH-27))s")${BLUE}║${RESET}${CLEAR_LINE}"
        # Clear any remaining lines from previous updates
        echo -ne "${CLEAR_LINE}\n${CLEAR_LINE}"
    else
        # Display each process with detailed info
        local line_count=0
        local output=""
        
        while IFS= read -r line; do
            # Extract PID and other basic info
            PID=$(echo "$line" | awk '{print $1}')
            CPU=$(echo "$line" | awk '{print $2}')
            MEM=$(echo "$line" | awk '{print $3}')
            CMD=$(echo "$line" | awk '{$1=$2=$3=""; print $0}' | sed 's/^[ \t]*//')
            
            # Get thread count
            THREADS=$(ps -o nlwp h -p "$PID" 2>/dev/null || echo "N/A")
            
            # Get CPU time
            CPU_TIME=$(ps -o time h -p "$PID" 2>/dev/null || echo "N/A")
            
            # Truncate command if too long
            MAX_CMD_LEN=$((TERM_WIDTH-48))
            if [ ${#CMD} -gt $MAX_CMD_LEN ]; then
                CMD="${CMD:0:$((MAX_CMD_LEN-3))}..."
            fi
            
            # Format output with colors based on usage
            output="${BLUE}║${RESET} "
            output+=$(printf "%-6s " "$PID")
            output+=$(printf "$(get_color $CPU)%-6.1f${RESET} " "$CPU")
            output+=$(printf "$(get_color $MEM)%-6.1f${RESET} " "$MEM")
            output+=$(printf "%-9s " "$THREADS")
            output+=$(printf "%-10s " "$CPU_TIME")
            output+=$(printf "%s" "$CMD")
            
            # Calculate padding for right border
            CMD_DISPLAY_LEN=${#CMD}
            if [ $CMD_DISPLAY_LEN -gt $MAX_CMD_LEN ]; then
                CMD_DISPLAY_LEN=$MAX_CMD_LEN
            fi
            PADDING=$((TERM_WIDTH-48-CMD_DISPLAY_LEN))
            output+=$(printf "%${PADDING}s" "")
            output+="${BLUE}║${RESET}"
            
            echo -e "$output${CLEAR_LINE}"
            ((line_count++))

            # Show per-core CPU usage for this Python process
            if [ $(echo "$CPU > 0.1" | bc) -eq 1 ]; then
                # Get per-core CPU usage for this process using taskset and top
                CORE_USAGE=""
                # Get affinity (which cores the process can run on)
                AFFINITY=$(taskset -cp "$PID" 2>/dev/null | grep -oP 'current affinity mask: \K.*' || echo "N/A")
                
                # If we can get affinity info, show per-core usage
                if [ "$AFFINITY" != "N/A" ]; then
                    output="${BLUE}║${RESET}   └─ CPU Cores: "
                    
                    # Use ps with -L to get thread info and calculate per-CPU usage
                    PS_THREADS=$(ps -L -o psr,pcpu -p "$PID" | grep -v PSR)
                    
                    # Create an array to store usage per core
                    declare -A core_usages
                    for i in $(seq 0 $((NUM_CORES-1))); do
                        core_usages[$i]=0
                    done
                    
                    # Sum usage for each core
                    while read -r thread_info; do
                        CORE_ID=$(echo "$thread_info" | awk '{print $1}')
                        THREAD_CPU=$(echo "$thread_info" | awk '{print $2}')
                        # Add this thread's CPU usage to its core
                        core_usages[$CORE_ID]=$(echo "${core_usages[$CORE_ID]} + $THREAD_CPU" | bc)
                    done <<< "$PS_THREADS"
                    
                    # Output core usage in a compact format
                    CORE_INFO=""
                    for i in $(seq 0 $((NUM_CORES-1))); do
                        # Round to one decimal place
                        USAGE=$(printf "%.1f" ${core_usages[$i]})
                        # Only show cores with usage > 0
                        if [ $(echo "$USAGE > 0" | bc) -eq 1 ]; then
                            CORE_INFO="${CORE_INFO}Core $i: $(get_color $USAGE)${USAGE}%${RESET} "
                        fi
                    done
                    
                    if [ -z "$CORE_INFO" ]; then
                        CORE_INFO="No significant per-core usage"
                    fi
                    
                    # Truncate if too long
                    MAX_CORE_INFO_LEN=$((TERM_WIDTH-25))
                    if [ ${#CORE_INFO} -gt $MAX_CORE_INFO_LEN ]; then
                        CORE_INFO="${CORE_INFO:0:$MAX_CORE_INFO_LEN}..."
                    fi
                    
                    output+="$CORE_INFO"
                    
                    # Calculate padding for right border
                    CORE_INFO_DISPLAY_LEN=${#CORE_INFO}
                    if [ $CORE_INFO_DISPLAY_LEN -gt $MAX_CORE_INFO_LEN ]; then
                        CORE_INFO_DISPLAY_LEN=$MAX_CORE_INFO_LEN
                    fi
                    PADDING=$((TERM_WIDTH-25-CORE_INFO_DISPLAY_LEN))
                    output+=$(printf "%${PADDING}s" "")
                    output+="${BLUE}║${RESET}"
                    
                    echo -e "$output${CLEAR_LINE}"
                    ((line_count++))
                fi
            fi
        done <<< "$PROCESS_DATA"
        
        # Save the number of lines we've displayed
        DISPLAYED_LINES=$line_count
    fi
    
    # Draw the bottom border
    echo -e "${BLUE}╚$(draw_line $((TERM_WIDTH-2)))╝${RESET}${CLEAR_LINE}"
    
    # Log to file if specified (without colors)
    if [ -n "$LOG_FILE" ]; then
        DATE=$(date "+%Y-%m-%d %H:%M:%S")
        TOTAL_CPU=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
        TOTAL_MEM=$(free | grep Mem | awk '{print $3/$2 * 100}')
        LOAD_AVG=$(cat /proc/loadavg | awk '{print $1" "$2" "$3}')
        
        {
            echo "--- $DATE ---"
            echo "System: CPU=${TOTAL_CPU}%, Memory=${TOTAL_MEM}%, Load=$LOAD_AVG"
            echo "Python Processes:"
            
            if [ -z "$PROCESS_DATA" ]; then
                echo "No Python processes found."
            else
                echo "PID    CPU%   MEM%   Threads   CPU Time   Command"
                echo "$PROCESS_DATA" | while read -r line; do
                    PID=$(echo "$line" | awk '{print $1}')
                    CPU=$(echo "$line" | awk '{print $2}')
                    MEM=$(echo "$line" | awk '{print $3}')
                    CMD=$(echo "$line" | awk '{$1=$2=$3=""; print $0}' | sed 's/^[ \t]*//')
                    THREADS=$(ps -o nlwp h -p "$PID" 2>/dev/null || echo "N/A")
                    CPU_TIME=$(ps -o time h -p "$PID" 2>/dev/null || echo "N/A")
                    
                    printf "%-6s %-6.1f %-6.1f %-9s %-10s %s\n" "$PID" "$CPU" "$MEM" "$THREADS" "$CPU_TIME" "$CMD"
                    
                    # Log per-core usage for processes with significant CPU usage
                    if [ $(echo "$CPU > 0.1" | bc) -eq 1 ]; then
                        # Get per-core usage similar to above but without color codes
                        PS_THREADS=$(ps -L -o psr,pcpu -p "$PID" | grep -v PSR)
                        
                        declare -A core_usages
                        for i in $(seq 0 $((NUM_CORES-1))); do
                            core_usages[$i]=0
                        done
                        
                        while read -r thread_info; do
                            CORE_ID=$(echo "$thread_info" | awk '{print $1}')
                            THREAD_CPU=$(echo "$thread_info" | awk '{print $2}')
                            core_usages[$CORE_ID]=$(echo "${core_usages[$CORE_ID]} + $THREAD_CPU" | bc)
                        done <<< "$PS_THREADS"
                        
                        CORE_INFO="  └─ CPU Cores: "
                        for i in $(seq 0 $((NUM_CORES-1))); do
                            USAGE=$(printf "%.1f" ${core_usages[$i]})
                            if [ $(echo "$USAGE > 0" | bc) -eq 1 ]; then
                                CORE_INFO="${CORE_INFO}Core $i: ${USAGE}% "
                            fi
                        done
                        
                        if [ "$CORE_INFO" != "  └─ CPU Cores: " ]; then
                            echo "$CORE_INFO"
                        fi
                    fi
                done
            fi
            echo ""
        } >> "$LOG_FILE"
    fi
}

monitor() {
    # Set up signal handling for clean exit
    trap "echo -e '\n${YELLOW}Monitoring stopped.${RESET}'; tput cnorm; exit 0" INT TERM
    
    # Hide cursor
    tput civis
    
    # Initial setup - draw the static parts of the UI
    initialize_screen
    
    while true; do
        # Update dynamic parts of the display
        update_timestamp
        update_system_stats
        update_processes
        
        # Wait for the specified interval
        sleep "$INTERVAL"
    done
}

# Start monitoring
monitor