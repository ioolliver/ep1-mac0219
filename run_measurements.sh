#! /bin/bash

set -euo pipefail
export LC_ALL=C

MEASUREMENTS=10
ITERATIONS=10
INITIAL_SIZE=16
OUTPUT_DIR=output

THREADS=(1 2 4 8 16 32)
RESUME=0
if [[ ${1:-} == --resume ]]; then
    RESUME=1
    shift
fi

if command -v perf >/dev/null 2>&1 && perf stat true >/dev/null 2>&1; then
    TIMER=perf
else
    TIMER=clock_gettime
    make wall_timer
fi
echo "Temporizador: $TIMER (tempo real decorrido)" >&2

trap 'rm -f "$OUTPUT_DIR/perf.tmp"' EXIT
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
    local KEY
    local EXECUTED=0

    ARGS="${COORDS[$REGION]} $SIZE"
    [[ $IO == no ]] && ARGS="$ARGS --benchmark"

    for ((run=1; run<=$MEASUREMENTS; run++)); do
        KEY="$NAME,$REGION,$SIZE,$NTHREADS,$IO,$run"
        if [[ ${DONE[$KEY]+present} ]]; then
            continue
        fi
        if ((EXECUTED == 0)); then
            echo "$NAME $REGION $SIZE threads=$NTHREADS io=$IO" >&2
        fi

        if [[ $TIMER == perf ]]; then
            if (cd "$OUTPUT_DIR" && OMP_NUM_THREADS=$NTHREADS perf stat ../"$NAME" $ARGS 2> perf.tmp > /dev/null); then
                TIME=$(awk '$2 == "seconds" && $3 == "time" && $4 == "elapsed" {print $1}' "$OUTPUT_DIR/perf.tmp")
            else
                TIME=
            fi
        else
            if (cd "$OUTPUT_DIR" && OMP_NUM_THREADS=$NTHREADS ../wall_timer ../"$NAME" $ARGS 2> perf.tmp > /dev/null); then
                TIME=$(awk '$1 == "TIME_S" {print $2}' "$OUTPUT_DIR/perf.tmp")
            else
                TIME=
            fi
        fi
        if [[ -z $TIME ]]; then
            echo "Erro: medição falhou para $NAME $REGION $SIZE threads=$NTHREADS io=$IO run=$run" >&2
            cat "$OUTPUT_DIR/perf.tmp" >&2
            exit 1
        fi
        if [[ ! $TIME =~ ^[0-9]+([.][0-9]+)?$ ]]; then
            echo "Erro: tempo inválido para $NAME $REGION $SIZE threads=$NTHREADS io=$IO run=$run" >&2
            cat "$OUTPUT_DIR/perf.tmp" >&2
            exit 1
        fi

        cat "$OUTPUT_DIR/perf.tmp" >> "$OUTPUT_DIR/$NAME/$REGION.log"
        echo "$NAME,$REGION,$SIZE,$NTHREADS,$IO,$run,$TIME" >> "$OUTPUT_DIR/$NAME/measurements.csv"
        DONE["$KEY"]=1
        EXECUTED=$((EXECUTED + 1))
    done

    if [[ $IO == yes ]]; then
        if ((EXECUTED > 0)); then
            mv "$OUTPUT_DIR/output.ppm" "$OUTPUT_DIR/images/${REGION}_${SIZE}.ppm"
        elif [[ ! -f $OUTPUT_DIR/images/${REGION}_${SIZE}.ppm ]]; then
            # A queda pode ter ocorrido depois da última linha do CSV e antes do mv.
            (cd "$OUTPUT_DIR" && ../mandelbrot_seq ${COORDS[$REGION]} "$SIZE")
            mv "$OUTPUT_DIR/output.ppm" "$OUTPUT_DIR/images/${REGION}_${SIZE}.ppm"
        fi
    fi
}

make
mkdir -p "$OUTPUT_DIR/images"

for NAME in "${NAMES[@]}"; do
    case $NAME in
        mandelbrot_seq|mandelbrot_pth|mandelbrot_omp) ;;
        *) echo "Versão desconhecida: $NAME" >&2; exit 1 ;;
    esac

    declare -A DONE=()
    CSV="$OUTPUT_DIR/$NAME/measurements.csv"
    if ((RESUME)) && [[ -f $CSV ]]; then
        while IFS=, read -r version region size threads io run time_s extra; do
            [[ $version == version ]] && continue
            if [[ $version != "$NAME" || ! $time_s =~ ^[0-9]+([.][0-9]+)?$ || ! $run =~ ^[0-9]+$ ]]; then
                echo "Linha inválida em $CSV: $version,$region,$size,$threads,$io,$run,$time_s" >&2
                exit 1
            fi
            KEY="$version,$region,$size,$threads,$io,$run"
            if [[ ${DONE[$KEY]+present} ]]; then
                echo "Medição duplicada em $CSV: $KEY" >&2
                exit 1
            fi
            DONE["$KEY"]=1
        done < "$CSV"
        echo "$NAME: ${#DONE[@]} medições já concluídas" >&2
    else
        rm -rf "$OUTPUT_DIR/$NAME"
        mkdir -p "$OUTPUT_DIR/$NAME"
        echo "version,region,size,threads,io,run,time_s" > "$CSV"
    fi
    mkdir -p "$OUTPUT_DIR/$NAME"

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

head -n 1 -q "$OUTPUT_DIR"/*/measurements.csv | head -n 1 > "$OUTPUT_DIR/measurements.csv"
tail -n +2 -q "$OUTPUT_DIR"/*/measurements.csv >> "$OUTPUT_DIR/measurements.csv"
