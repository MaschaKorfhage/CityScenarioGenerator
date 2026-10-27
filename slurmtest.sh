#!/usr/bin/zsh 

### Job Parameters 
#SBATCH --ntasks=1
#SBATCH --time=00:10:00
#SBATCH --job-name=generator
#SBATCH --partition=c23ms
#SBATCH --mem=5G
#SBATCH --output="slurm/generator_%A.out"
#SBATCH --mail-type=ALL
#SBATCH -A thes2412

### Program Code

source /home/gzi37280/CityScenarioGenerator/.cityvenv/bin/activate

srun python cityscenariogenerator/main.py --city "Jülich" --street "Große Rurstr." --pharmacy-source custom