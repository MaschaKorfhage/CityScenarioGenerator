#!/usr/bin/zsh 

### Job Parameters 
#SBATCH --ntasks=1              # Ask for 8 MPI tasks
#SBATCH --time=01:00:00         # Run time of 15 minutes
#SBATCH --job-name=generator  # Sets the job name
#SBATCH --output=output.txt     # redirects stdout and stderr to stdout.txt

### Program Code

source /home/gzi37280/CityScenarioGenerator/.cityvenv/bin/activate

srun python cityscenariogenerator/main.py --city "Jülich"