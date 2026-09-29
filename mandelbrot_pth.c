#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <pthread.h>
#include <string.h>

double c_x_min;
double c_x_max;
double c_y_min;
double c_y_max;

double pixel_width;
double pixel_height;

int iteration_max = 200;

int image_size;
unsigned char (*image_buffer)[3];

int i_x_max;
int i_y_max;
int image_buffer_size;

int gradient_size = 16;
int colors[17][3] = {
                        {66, 30, 15},
                        {25, 7, 26},
                        {9, 1, 47},
                        {4, 4, 73},
                        {0, 7, 100},
                        {12, 44, 138},
                        {24, 82, 177},
                        {57, 125, 209},
                        {134, 181, 229},
                        {211, 236, 248},
                        {241, 233, 191},
                        {248, 201, 95},
                        {255, 170, 0},
                        {204, 128, 0},
                        {153, 87, 0},
                        {106, 52, 3},
                        {16, 16, 16},
                    };

int benchmark_mode = 0;
int show_checksum = 0;
volatile unsigned long long benchmark_checksum = 0;
 
int num_threads = 32;
const int num_thread_rows = 10;  // numero de linhas processadas por vez

int next_row = 0;
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;


void allocate_image_buffer(){
    image_buffer = malloc((size_t)image_buffer_size * sizeof(*image_buffer));
    if (image_buffer == NULL) {
        fprintf(stderr, "Erro: não foi possível alocar a imagem.\n");
        exit(EXIT_FAILURE);
    }
};

void init(int argc, char *argv[]){
    if(argc < 6){
        printf("usage: ./mandelbrot_pth c_x_min c_x_max c_y_min c_y_max image_size\n");
        printf("examples with image_size = 11500:\n");
        printf("    Full Picture:         ./mandelbrot_pth -2.5 1.5 -2.0 2.0 11500\n");
        printf("    Seahorse Valley:      ./mandelbrot_pth -0.8 -0.7 0.05 0.15 11500\n");
        printf("    Elephant Valley:      ./mandelbrot_pth 0.175 0.375 -0.1 0.1 11500\n");
        printf("    Triple Spiral Valley: ./mandelbrot_pth -0.188 -0.012 0.554 0.754 11500\n");
        exit(0);
    }
    else{
        sscanf(argv[1], "%lf", &c_x_min);
        sscanf(argv[2], "%lf", &c_x_max);
        sscanf(argv[3], "%lf", &c_y_min);
        sscanf(argv[4], "%lf", &c_y_max);
        sscanf(argv[5], "%d", &image_size);

        i_x_max           = image_size;
        i_y_max           = image_size;
        image_buffer_size = image_size * image_size;

        pixel_width       = (c_x_max - c_x_min) / i_x_max;
        pixel_height      = (c_y_max - c_y_min) / i_y_max;
    };
};

void update_rgb_buffer(int iteration, int x, int y){
    int color;

    if(iteration == iteration_max){
        image_buffer[(i_y_max * y) + x][0] = colors[gradient_size][0];
        image_buffer[(i_y_max * y) + x][1] = colors[gradient_size][1];
        image_buffer[(i_y_max * y) + x][2] = colors[gradient_size][2];
    }
    else{
        color = iteration % gradient_size;

        image_buffer[(i_y_max * y) + x][0] = colors[color][0];
        image_buffer[(i_y_max * y) + x][1] = colors[color][1];
        image_buffer[(i_y_max * y) + x][2] = colors[color][2];
    };
};

void write_to_file(){
    FILE * file;
    char * filename               = "output.ppm";
    char * comment                = "# ";

    int max_color_component_value = 255;

    file = fopen(filename,"wb");
    if (file == NULL) {
        perror("Erro ao abrir output.ppm");
        exit(EXIT_FAILURE);
    }

    fprintf(file, "P6\n %s\n %d\n %d\n %d\n", comment,
            i_x_max, i_y_max, max_color_component_value);

    if (fwrite(image_buffer, sizeof(*image_buffer), (size_t)image_buffer_size, file)
        != (size_t)image_buffer_size) {
        perror("Erro ao gravar a imagem");
        fclose(file);
        exit(EXIT_FAILURE);
    }

    free(image_buffer);
    image_buffer = NULL;
    if (fclose(file) != 0) {
        perror("Erro ao fechar output.ppm");
        exit(EXIT_FAILURE);
    }
};

void *compute_mandelbrot(void *arg){
    double z_x;
    double z_y;
    double z_x_squared;
    double z_y_squared;
    double escape_radius_squared = 4;
    unsigned long long checksum = 0;

    int iteration;
    int i_x;
    int i_y;

    double c_x;
    double c_y;

    while (1) {
        pthread_mutex_lock(&mutex);
        int start = next_row;
        next_row += num_thread_rows;
        pthread_mutex_unlock(&mutex);

        if (start >= i_y_max) break;

        int end = start + num_thread_rows;
        if (end >= i_y_max) end = i_y_max;

        for (i_y = start; i_y < end; i_y++) {
            c_y = c_y_min + i_y * pixel_height;

            if (fabs(c_y) < pixel_height / 2) {
                c_y = 0.0;
            };

            for (i_x = 0; i_x < i_x_max; i_x++) {
                c_x = c_x_min + i_x * pixel_width;

                z_x = 0.0;
                z_y = 0.0;

                z_x_squared = 0.0;
                z_y_squared = 0.0;

                for (iteration = 0;
                     iteration < iteration_max &&
                     ((z_x_squared + z_y_squared) < escape_radius_squared);
                     iteration++) {
                    z_y = 2 * z_x * z_y + c_y;
                    z_x = z_x_squared - z_y_squared + c_x;

                    z_x_squared = z_x * z_x;
                    z_y_squared = z_y * z_y;
                };

                if (benchmark_mode) {
                    checksum += (unsigned long long)iteration;
                } else {
                    update_rgb_buffer(iteration, i_x, i_y);
                }
            };
        };
    }

    if (benchmark_mode) {
        pthread_mutex_lock(&mutex);
        benchmark_checksum += checksum;
        pthread_mutex_unlock(&mutex);
    }

    return NULL;
};

int main(int argc, char *argv[]){
    init(argc, argv);

    if (argc == 7) {
        if (strcmp(argv[6], "--benchmark") == 0) {
            benchmark_mode = 1;
        } else if (strcmp(argv[6], "--benchmark-check") == 0) {
            benchmark_mode = 1;
            show_checksum = 1;
        } else {
            fprintf(stderr, "Opção desconhecida: %s\n", argv[6]);
            return 1;
        }
    } else if (argc != 6) {
        fprintf(stderr, "Uso: %s cx_min cx_max cy_min cy_max tamanho [--benchmark|--benchmark-check]\n",
                argv[0]);
        return 1;
    }
  
    char *threads_env = getenv("OMP_NUM_THREADS");
    if (threads_env != NULL) {
      num_threads = atoi(threads_env);
  }
    if (num_threads < 1 || num_threads > 32) {
        fprintf(stderr, "Erro: OMP_NUM_THREADS deve estar entre 1 e 32.\n");
        return 1;
    }

    if (!benchmark_mode) {
        allocate_image_buffer();
    }
    
    pthread_t threads[32];
    for (int i=0; i<num_threads; i++) {
        int err = pthread_create(&threads[i], NULL, compute_mandelbrot, NULL);
        if (err != 0) {
            fprintf(stderr, "Erro em pthread_create: %s\n", strerror(err));
            return 1;
        }
    }
    for (int i=0; i<num_threads; i++) pthread_join(threads[i], NULL);

    pthread_mutex_destroy(&mutex);

    if (!benchmark_mode) {
        write_to_file();
    } else if (show_checksum) {
        printf("%llu\n", benchmark_checksum);
    }

    return 0;
};
