#! /bin/bash

set -euo pipefail
export LC_ALL=C

MEASUREMENTS=10
ITERATIONS=10
INITIAL_SIZE=16

THREADS=(1 2 4 8 16 32)

if command -v perf >/dev/null 2>&1 && perf stat true >/dev/null 2>&1; then
    TIMER=perf
else
    TIMER=clock_gettime
    make wall_timer
fi
echo "Temporizador: $TIMER (tempo real decorrido)" >&2

trap 'rm -f perf.tmp' EXIT
if (($#)); then
    NAMES=("$@")
else
    NAMES=(mandelbrot_seq mandelbrot_pth mandelbrot_omp)
fi
REGIONS=('full' 'seahorse' 'elephant' 'triple_spiral')

declare -A COORDS=(
    [full]='-2.5 1.5 -2.0 2.0'
    [seahorse]='-0.8 -0.7 0.05 0.15'
    [elephant]='0.175 0.375 -0.1 0.1'
    [triple_spiral]='-0.188 -0.012 0.554 0.754'
)

measure() {
    local NAME=$1
    local REGION=$2
    local SIZE=$3
    local NTHREADS=$4
    local IO=$5
    local ARGS
    local TIME

    ARGS="${COORDS[$REGION]} $SIZE"
    [[ $IO == no ]] && ARGS="$ARGS --benchmark"

    echo "$NAME $REGION $SIZE threads=$NTHREADS io=$IO" >&2

    for ((run=1; run<=$MEASUREMENTS; run++)); do
        if [[ $TIMER == perf ]]; then
            if OMP_NUM_THREADS=$NTHREADS perf stat ./"$NAME" $ARGS 2> perf.tmp > /dev/null; then
                TIME=$(awk '$2 == "seconds" && $3 == "time" && $4 == "elapsed" {print $1}' perf.tmp)
            else
                TIME=
            fi
        else
            if OMP_NUM_THREADS=$NTHREADS ./wall_timer ./"$NAME" $ARGS 2> perf.tmp > /dev/null; then
                TIME=$(awk '$1 == "TIME_S" {print $2}' perf.tmp)
            else
                TIME=
            fi
        fi
        if [[ -z $TIME ]]; then
            echo "Erro: medição falhou para $NAME $REGION $SIZE threads=$NTHREADS io=$IO run=$run" >&2
            cat perf.tmp >&2
            exit 1
        fi
        if [[ ! $TIME =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            echo "Erro: tempo inválido para $NAME $REGION $SIZE threads=$NTHREADS io=$IO run=$run" >&2
            cat perf.tmp >&2
            exit 1
        fi

        cat perf.tmp >> "results/$NAME/$REGION.log"
        echo "$NAME,$REGION,$SIZE,$NTHREADS,$IO,$run,$TIME" >> "results/$NAME/measurements.csv"
    done
}

make
mkdir -p results

for NAME in "${NAMES[@]}"; do
    rm -rf "results/$NAME"
    mkdir "results/$NAME"
    echo "version,region,size,threads,io,run,time_s" > "results/$NAME/measurements.csv"

    SIZE=$INITIAL_SIZE

    for ((i=1; i<=$ITERATIONS; i++)); do
        for REGION in "${REGIONS[@]}"; do
            if [[ $NAME == mandelbrot_seq ]]; then
                measure "$NAME" "$REGION" "$SIZE" 1 yes
                measure "$NAME" "$REGION" "$SIZE" 1 no
            else
                for NTHREADS in "${THREADS[@]}"; do
                    measure "$NAME" "$REGION" "$SIZE" "$NTHREADS" no
                done
            fi
        done

        SIZE=$(($SIZE * 2))
    done
done

head -n 1 -q results/*/measurements.csv | head -n 1 > results/measurements.csv
tail -n +2 -q results/*/measurements.csv >> results/measurements.csv

rm -f output.ppm
