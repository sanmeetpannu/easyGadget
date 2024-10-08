import subprocess
import sys
import os
import xml.etree.ElementTree as ET
import argparse
import shutil
import tempfile
from colorama import init, Fore, Style

init(autoreset=True)  # Initialize colorama

VERSION = "v1"
AUTHOR = "Sannmeet Pannu"

BANNER = f"""
{Fore.CYAN}╔═══╗{Fore.GREEN}╔═══╗{Fore.YELLOW}╔═══╗{Fore.RED}╔╗  ╔╗{Fore.MAGENTA}╔═══╗{Fore.BLUE}╔═══╗{Fore.CYAN}╔═══╗{Fore.GREEN}╔═══╗{Fore.WHITE}╔═══╗{Fore.CYAN}╔════╗
{Fore.CYAN}║╔══╝{Fore.GREEN}║╔═╗║{Fore.YELLOW}║╔═╗║{Fore.RED}║╚╗╔╝║{Fore.MAGENTA}║╔══╝{Fore.BLUE}║╔═╗║{Fore.CYAN}║╔═╗║{Fore.GREEN}║╔══╝{Fore.WHITE}║╔══╝{Fore.CYAN}║╔╗╔╗║
{Fore.CYAN}║╚══╗{Fore.GREEN}║║ ║║{Fore.YELLOW}║╚══╗{Fore.RED}╚╗║║╔╝{Fore.MAGENTA}║║╔═╗{Fore.BLUE}║║ ║║{Fore.CYAN}║║ ║║{Fore.GREEN}║║╔═╗{Fore.WHITE}║╚══╗{Fore.CYAN}╚╝║║╚╝
{Fore.CYAN}║╔══╝{Fore.GREEN}║╚═╝║{Fore.YELLOW}╚══╗║{Fore.RED} ║╚╝║ {Fore.MAGENTA}║║╚╗║{Fore.BLUE}║╚═╝║{Fore.CYAN}║║ ║║{Fore.GREEN}║║╚╗║{Fore.WHITE}║╔══╝{Fore.CYAN}  ║║  
{Fore.CYAN}║╚══╗{Fore.GREEN}║╔═╗║{Fore.YELLOW}║╚═╝║{Fore.RED} ╚╗╔╝ {Fore.MAGENTA}║╚═╝║{Fore.BLUE}║╔═╗║{Fore.CYAN}║╚═╝║{Fore.GREEN}║╚═╝║{Fore.WHITE}║╚══╗{Fore.CYAN}  ║║  
{Fore.CYAN}╚═══╝{Fore.GREEN}╚╝ ╚╝{Fore.YELLOW}╚═══╝{Fore.RED}  ╚╝  {Fore.MAGENTA}╚═══╝{Fore.BLUE}╚╝ ╚╝{Fore.CYAN}╚═══╝{Fore.GREEN}╚═══╝{Fore.WHITE}╚═══╝{Fore.CYAN}  ╚╝  
{Fore.WHITE}EasyGadget {VERSION} by {AUTHOR}
"""

def run_command(command, show_output=False):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
    output = []
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            output.append(line.strip())
            if show_output:
                print(line.strip())
    return process.returncode == 0, '\n'.join(output)

def is_tool_installed(tool_name):
    command = f"command -v {tool_name}"
    return run_command(command)[0]

def log_error(message):
    print(f"{Fore.RED}ERROR: {message}{Style.RESET_ALL}", file=sys.stderr)

def log_success(message):
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")

def log_info(message):
    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

def check_required_tools():
    tools = ['apktool', 'aapt', 'keytool', 'apksigner']
    missing_tools = []
    for tool in tools:
        if not is_tool_installed(tool):
            missing_tools.append(tool)
    return missing_tools

def decompile_apk(apk_path, output_dir, with_resources=True, show_logs=False):
    print(f"{'Decompiling APK...' if with_resources else 'Decompiling APK without resources...'}", end=' ', flush=True)
    cmd = f"apktool d -f {'-r' if not with_resources else ''} -o {output_dir} {apk_path}"
    success, output = run_command(cmd, show_logs)
    if success:
        log_success("Success")
    else:
        log_error("Failed")
    return success

def get_main_activity(manifest_path):
    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
        namespace = {'android': 'http://schemas.android.com/apk/res/android'}
        for activity in root.findall('.//activity', namespace):
            for intent_filter in activity.findall('intent-filter', namespace):
                action = intent_filter.find('action', namespace)
                category = intent_filter.find('category', namespace)
                if action is not None and action.get('{http://schemas.android.com/apk/res/android}name') == 'android.intent.action.MAIN':
                    if category is not None and category.get('{http://schemas.android.com/apk/res/android}name') == 'android.intent.category.LAUNCHER':
                        return activity.get('{http://schemas.android.com/apk/res/android}name')
    except ET.ParseError as e:
        log_error(f"Failed to parse AndroidManifest.xml: {e}")
    return None

def insert_frida_loader(smali_file_path):
    print("Inserting Frida loader...", end=' ', flush=True)
    frida_load_code = '''
    const-string v0, "frida"
    invoke-static {v0}, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
'''

    try:
        with open(smali_file_path, 'r') as smali_file:
            content = smali_file.readlines()

        new_content = []
        clinit_found = False
        frida_loader_added = False

        for idx, line in enumerate(content):
            new_content.append(line)

            # Log each line read from the file
            print(f"Processing line {idx + 1}: {line.strip()}")

            # Check if the current line defines the <clinit> method
            if line.strip().startswith('.method public static constructor <clinit>()V'):
                print(f"[LOG] Found <clinit> at line {idx + 1}")
                clinit_found = True
                # Add the Frida load code right after the method definition
                new_content.append(frida_load_code)
                frida_loader_added = True
                print(f"[LOG] Frida load code added at line {idx + 2}")

            elif clinit_found and line.strip() == '.end method':
                # Insert the Frida loader just before the end of the method if missed
                print(f"[LOG] Reached end of <clinit> at line {idx + 1}. Adding Frida code before .end method")
                if not frida_loader_added:  # Check if it was already added
                    new_content.insert(-1, frida_load_code)
                    frida_loader_added = True

        # If <clinit> method was not found, create it
        if not clinit_found:
            print("[LOG] <clinit> method not found, creating new one")
            new_clinit_method = f'''
.method public static constructor <clinit>()V
    .registers 1
{frida_load_code}
    return-void
.end method
'''
            new_content.append(new_clinit_method)
            frida_loader_added = True
            print("[LOG] New <clinit> method with Frida load code added at the end of the file")

        # Write the changes back to the file if any modifications were made
        if frida_loader_added:
            with open(smali_file_path, 'w') as smali_file:
                smali_file.writelines(new_content)
            print("[SUCCESS] Frida loader inserted successfully")
            return True
        else:
            print("[ERROR] Failed to add Frida loader")
            log_error("Could not find appropriate location to insert Frida loader")
            return False

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        log_error(f"Failed to insert Frida loader: {e}")
        return False


def copy_frida_libs(gadget_dir, output_dir, target_arch):
    print("Copying Frida libraries...", end=' ', flush=True)
    try:
        arch_dir = os.path.join(output_dir, 'lib', target_arch)
        os.makedirs(arch_dir, exist_ok=True)

        libfrida = os.path.join(gadget_dir, f'{target_arch}', 'libfrida.so')
        libfrida_config = os.path.join(gadget_dir, f'{target_arch}', 'libfrida.config.so')

        if os.path.exists(libfrida):
            shutil.copy2(libfrida, os.path.join(arch_dir, 'libfrida.so'))
        else:
            raise FileNotFoundError(f"{libfrida} not found.")

        if os.path.exists(libfrida_config):
            shutil.copy2(libfrida_config, os.path.join(arch_dir, 'libfrida.config.so'))
        else:
            raise FileNotFoundError(f"{libfrida_config} not found.")

        print("Success")
        return True
    except Exception as e:
        print("Failed")
        log_error(str(e))
        return False

def copy_and_rename_script(script_path, output_dir, target_arch):
    print("Copying and renaming script...", end=' ', flush=True)
    try:
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script file not found: {script_path}")

        arch_dir = os.path.join(output_dir, 'lib', target_arch)
        os.makedirs(arch_dir, exist_ok=True)

        dest_path = os.path.join(arch_dir, 'libscript.so')
        shutil.copy2(script_path, dest_path)
        
        print("Success")
        return True
    except Exception as e:
        print("Failed")
        log_error(str(e))
        return False

def recompile_apk(output_dir, apk_name, show_logs=False):
    print("Recompiling APK...", end=' ', flush=True)
    apktool_cmd = f"apktool b {output_dir} -o {apk_name}"
    success, output = run_command(apktool_cmd, show_logs)
    print("Success" if success else "Failed")
    return success

def sign_apk(apk_path, show_logs=False):
    print("Signing APK...", end=' ', flush=True)
    keystore_path = os.path.join(os.path.dirname(__file__), 'debug.keystore')
    if not os.path.exists(keystore_path):
        keytool_cmd = (
            f"keytool -genkey -v -keystore {keystore_path} -storepass android -alias androiddebugkey "
            f"-keypass android -keyalg RSA -keysize 2048 -validity 10000 "
            f"-dname \"CN=Android Debug,O=Android,C=US\""
        )
        success, output = run_command(keytool_cmd, show_logs)
        if not success:
            print("Failed")
            log_error("Failed to create debug keystore.")
            return False

    apksigner_cmd = (
        f"apksigner sign --ks {keystore_path} --ks-key-alias androiddebugkey "
        f"--ks-pass pass:android --key-pass pass:android {apk_path}"
    )
    
    success, output = run_command(apksigner_cmd, show_logs)
    print("Success" if success else "Failed")
    return success
def cleanup(temp_dir):
    print("Cleaning up temporary files...", end=' ', flush=True)
    try:
        shutil.rmtree(temp_dir)
        print("Success")
    except Exception as e:
        print("Failed")
        log_error(f"Failed to clean up temporary files: {e}")

def main():
    parser = argparse.ArgumentParser(description='EasyGadget: Patch APKs with Frida for easy instrumentation')
    parser.add_argument('-a', '--apk', required=True, help='Path to the APK file to patch')
    parser.add_argument('--arch', choices=['armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64'], 
                        required=True, help='Target architecture')
    parser.add_argument('--script', help='Path to the script.js file to be included in the APK')
    parser.add_argument('--logs', action='store_true', help='Show detailed logs')

    args = parser.parse_args()

    print(BANNER)

    missing_tools = check_required_tools()
    if missing_tools:
        log_error(f"The following required tools are not installed: {', '.join(missing_tools)}")
        log_error("Please install these tools manually before running the script.")
        sys.exit(1)
    
    temp_dir = tempfile.mkdtemp()
    try:
        if not decompile_apk(args.apk, temp_dir, with_resources=True, show_logs=args.logs):
            raise Exception("Failed to decompile APK with resources")

        manifest_path = os.path.join(temp_dir, "AndroidManifest.xml")
        main_activity = get_main_activity(manifest_path)
        
        if not main_activity:
            raise Exception("Could not find the main activity")

        log_info(f"Main activity: {main_activity}")
        
        if not decompile_apk(args.apk, temp_dir, with_resources=False, show_logs=args.logs):
            raise Exception("Failed to decompile APK without resources")

        activity_smali_path = os.path.join(temp_dir, 'smali', main_activity.replace('.', '/')) + '.smali'
        
        if not insert_frida_loader(activity_smali_path):
            raise Exception("Failed to insert Frida loader")

        gadget_directory = os.path.join(os.path.dirname(__file__), 'gadget')
        if not copy_frida_libs(gadget_directory, temp_dir, args.arch):
            raise Exception("Failed to copy Frida libraries")

        if args.script:
            if not copy_and_rename_script(args.script, temp_dir, args.arch):
                raise Exception("Failed to copy and rename script")

        apk_name = os.path.basename(args.apk)
        output_apk = os.path.join(os.path.dirname(args.apk), f"{os.path.splitext(apk_name)[0]}_mod.apk")
        
        if not recompile_apk(temp_dir, output_apk, show_logs=args.logs):
            raise Exception("Failed to recompile the APK")

        if not sign_apk(output_apk, show_logs=args.logs):
            raise Exception("Failed to sign the APK")

        log_success(f"Successfully patched APK: {output_apk}")

    except Exception as e:
        log_error(str(e))
    finally:
        cleanup(temp_dir)

if __name__ == "__main__":
    main()
        
