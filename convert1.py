import os
import subprocess
import argparse

def reduce_fps(input_path, output_path=None, target_fps=6):
    """
    Reduce the frames per second of an MP4 video to the target FPS.
    
    Args:
        input_path (str): Path to the input video file
        output_path (str, optional): Path for the output video file. If None, a default name will be generated
        target_fps (int, optional): Target frames per second. Defaults to 6
        
    Returns:
        str: Path to the output video file
    """
    # Check if input file exists
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Generate output filename if not provided
    if output_path is None:
        filename, ext = os.path.splitext(input_path)
        output_path = f"{filename}_{target_fps}fps{ext}"
    
    # Build the ffmpeg command
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-c:v", "libx264",    # Video codec
        "-crf", "23",         # Quality factor (0-51, lower is better)
        "-r", str(target_fps),  # Target frame rate
        "-c:a", "copy",       # Copy audio without re-encoding
        "-y",                 # Overwrite output file if it exists
        output_path
    ]
    
    # Execute the command
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Successfully converted video to {target_fps} FPS: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")
        print(f"ffmpeg error output: {e.stderr.decode()}")
        raise
    except FileNotFoundError:
        print("ffmpeg is not installed or not found in the system path.")
        print("Please install ffmpeg before using this script.")
        raise

if __name__ == "__main__":
    # Create argument parser
    parser = argparse.ArgumentParser(description="Reduce video FPS to 6 frames per second")
    parser.add_argument("input", help="Path to the input video file")
    parser.add_argument("-o", "--output", help="Path for the output video file (optional)")
    parser.add_argument("-f", "--fps", type=int, default=6, help="Target FPS (default: 6)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Call the function
    reduce_fps(args.input, args.output, args.fps)
