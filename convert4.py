import os
import subprocess
import argparse
import json
import platform
import sys
import time
from pathlib import Path


class VideoProcessingError(Exception):
    """Base exception class for all video processing errors."""
    
    def __init__(self, message, command=None, exit_code=None, stderr=None):
        self.message = message
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(self.message)


def detect_platform():
    """
    Detect the operating system platform.
    
    Returns:
        str: 'windows' or 'linux' or 'other'
    """
    system = platform.system().lower()
    if system == 'windows':
        return 'windows'
    elif system == 'linux':
        return 'linux'
    else:
        return 'other'


def normalize_path(file_path):
    """
    Normalize a file path for the current operating system.
    
    Args:
        file_path (str): Original file path
        
    Returns:
        Path: Normalized path object
    """
    # Convert to Path object which handles different OS path separators
    return Path(file_path).absolute()


def is_file_locked(file_path):
    """
    Check if a file is locked (Windows-specific).
    
    Args:
        file_path (str or Path): Path to the file to check
        
    Returns:
        bool: True if file is locked, False otherwise
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return False
        
    try:
        # Try to open the file in read and write mode
        with open(file_path, 'a+b') as f:
            # If we can open it, it's not locked
            pass
        return False
    except (IOError, PermissionError):
        # If we get an error, the file is locked
        return True


def wait_for_file_unlock(file_path, timeout=30, check_interval=0.5):
    """
    Wait for a file to be unlocked, with timeout.
    
    Args:
        file_path (str or Path): Path to the file to check
        timeout (int): Maximum time to wait in seconds
        check_interval (float): Time between checks in seconds
        
    Returns:
        bool: True if file became unlocked, False if still locked after timeout
    """
    file_path = Path(file_path)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if not is_file_locked(file_path):
            return True
        time.sleep(check_interval)
    
    return False


def check_ffmpeg():
    """
    Check if ffmpeg and ffprobe are installed and available.
    
    Returns:
        bool: True if both are available, False otherwise
    """
    try:
        # Check ffmpeg
        subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        
        # Check ffprobe
        subprocess.run(
            ["ffprobe", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_video_duration(video_path):
    """
    Get the duration of a video file in seconds.
    
    Args:
        video_path (str): Path to the video file
        
    Returns:
        float: Duration of the video in seconds
    """
    video_path = str(Path(video_path))  # Normalize path
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except (subprocess.CalledProcessError, KeyError, json.JSONDecodeError) as e:
        print(f"Error getting video duration: {e}")
        return 0


def format_duration(seconds):
    """
    Format seconds into minutes and seconds.
    
    Args:
        seconds (float): Duration in seconds
        
    Returns:
        str: Formatted duration as "MM:SS"
    """
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def reduce_fps(input_path, output_path=None, target_fps=6, reduce_quality=True):
    """
    Reduce the frames per second of an MP4 video to the target FPS and optionally lower quality.
    
    Args:
        input_path (str): Path to the input video file
        output_path (str, optional): Path for the output video file. If None, a default name will be generated
        target_fps (int, optional): Target frames per second. Defaults to 6
        reduce_quality (bool, optional): If True, also reduces quality to minimize file size. Defaults to True
        
    Returns:
        str: Path to the output video file
    """
    # Normalize input path
    input_path = normalize_path(input_path)
    
    # Check if input file exists
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Check if ffmpeg is available
    if not check_ffmpeg():
        print("Error: ffmpeg and/or ffprobe are not installed or not found in the system path.")
        print("Please install ffmpeg before using this script.")
        print("  - Windows: Download from https://ffmpeg.org/download.html")
        print("  - Debian/Ubuntu: sudo apt install ffmpeg")
        sys.exit(1)
    
    # Get original video info
    original_duration = get_video_duration(str(input_path))
    original_duration_formatted = format_duration(original_duration)
    original_size = input_path.stat().st_size / (1024 * 1024)  # Size in MB
    print(f"Original video duration: {original_duration_formatted} (MM:SS)")
    print(f"Original file size: {original_size:.2f} MB")
    
    # Generate output filename if not provided
    if output_path is None:
        quality_suffix = "_lq" if reduce_quality else ""
        output_path = input_path.with_name(f"{input_path.stem}_{target_fps}fps{quality_suffix}{input_path.suffix}")
    else:
        output_path = normalize_path(output_path)
    
    # Delete output file if it already exists to avoid file lock issues
    if output_path.exists():
        try:
            if is_file_locked(output_path):
                print(f"Warning: Output file {output_path} is locked. Waiting for it to be released...")
                if not wait_for_file_unlock(output_path, timeout=10):
                    raise VideoProcessingError(f"Output file {output_path} is locked by another process and cannot be overwritten.")
            output_path.unlink()
            print(f"Removed existing output file: {output_path}")
        except PermissionError as e:
            raise VideoProcessingError(f"Cannot delete existing output file {output_path}: {str(e)}")
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build the ffmpeg command
    cmd = ["ffmpeg", "-i", str(input_path)]
    
    # Video settings
    cmd.extend(["-c:v", "libx264"])  # Video codec
    cmd.extend(["-r", str(target_fps)])  # Target frame rate
    
    if reduce_quality:
        cmd.extend(["-crf", "28"])  # Higher CRF means lower quality (0-51)
        cmd.extend(["-preset", "medium"])  # Encoding speed/compression ratio
        cmd.extend(["-vf", "scale=iw/2:ih/2"])  # Reduce resolution by half
        cmd.extend(["-c:a", "aac"])  # Re-encode audio with AAC codec
        cmd.extend(["-b:a", "64k"])  # Reduce audio bitrate
        cmd.extend(["-ac", "1"])  # Convert to mono audio
    else:
        cmd.extend(["-crf", "23"])  # Standard quality
        cmd.extend(["-c:a", "copy"])  # Copy audio without re-encoding
    
    # Output file
    cmd.extend(["-y", str(output_path)])  # Overwrite output file if it exists
    
    # Execute the command
    try:
        print(f"Starting video conversion process... (This may take a while)")
        
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=1800  # 30 minute timeout
        )
        
        # Explicitly wait for the file to be fully released on Windows
        platform_type = detect_platform()
        if platform_type == 'windows':
            print("Ensuring file handle is released...")
            # Force garbage collection to release file handles
            import gc
            gc.collect()
            
            # Wait for the file to be unlocked
            if is_file_locked(output_path):
                print(f"Waiting for output file to be fully released...")
                if not wait_for_file_unlock(output_path, timeout=15):
                    print(f"Warning: Output file may still be locked by another process.")
        
        # Get converted video info
        converted_duration = get_video_duration(str(output_path))
        converted_duration_formatted = format_duration(converted_duration)
        converted_size = output_path.stat().st_size / (1024 * 1024)  # Size in MB
        
        print(f"Successfully converted video to {target_fps} FPS: {output_path}")
        print(f"Converted video duration: {converted_duration_formatted} (MM:SS)")
        print(f"Converted file size: {converted_size:.2f} MB")
        
        # Calculate size reduction percentage
        size_reduction = ((original_size - converted_size) / original_size) * 100
        print(f"File size reduction: {size_reduction:.1f}%")
        
        # Calculate duration difference
        duration_diff = abs(original_duration - converted_duration)
        if duration_diff > 1:  # Only show if difference is more than 1 second
            diff_formatted = format_duration(duration_diff)
            if original_duration > converted_duration:
                print(f"Duration decreased by: {diff_formatted} (MM:SS)")
            else:
                print(f"Duration increased by: {diff_formatted} (MM:SS)")
        
        return str(output_path)
        
    except subprocess.TimeoutExpired:
        raise VideoProcessingError(f"Conversion timed out after 30 minutes")
    except subprocess.CalledProcessError as e:
        raise VideoProcessingError(f"Conversion failed", cmd, e.returncode, e.stderr)
    except Exception as e:
        raise VideoProcessingError(f"Unexpected error: {str(e)}", cmd)


if __name__ == "__main__":
    # Detect platform
    platform_type = detect_platform()
    print(f"Detected platform: {platform_type}")
    
    # Create argument parser
    parser = argparse.ArgumentParser(description="Reduce video FPS and optionally degrade quality to reduce file size")
    parser.add_argument("input", help="Path to the input video file")
    parser.add_argument("-o", "--output", help="Path for the output video file (optional)")
    parser.add_argument("-f", "--fps", type=int, default=6, help="Target FPS (default: 6)")
    parser.add_argument("-q", "--quality", action="store_true", default=True, 
                        help="Reduce quality to minimize file size (default: True)")
    parser.add_argument("--keep-quality", action="store_false", dest="quality",
                        help="Keep original quality, only reduce FPS")
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        # Call the function
        output_file = reduce_fps(args.input, args.output, args.fps, args.quality)
        print(f"\nProcess completed successfully. Output saved to:\n{output_file}")
    except VideoProcessingError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)
