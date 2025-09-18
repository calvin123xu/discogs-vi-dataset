#!/encs/bin/bash
#SBATCH --job-name=DISCOGS-VI-download
#SBATCH --account=weiping
#SBATCH --output=DISCOGS-VI-slurm-%j.out
#SBATCH --mail-type=ALL
#SBATCH --mail-user=x_qiaoyu@speed.encs.concordia.ca
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=20G
#SBATCH -p pt
#SBATCH --time=01:00:00

# 环境设置
cd /speed-scratch/qiaoyu/speed-hpc/project/discogs-vi-dataset

source /encs/pkg/anaconda3-2023.03/root/etc/profile.d/conda.sh
conda activate /speed-scratch/qiaoyu/speed-hpc/env/discogs-vi-dataset

# 运行下载脚本
srun python discogs_vi_yt/audio_download_yt/download_missing_version_youtube_urls.py \
    metadata/Discogs-VI-YT-20240701.jsonl.split.00 music_dir/
