# Windows PowerShell Beginner Guide

This guide is for people who have never used PowerShell or a command line before.
It uses plain English throughout. No technical jargon.
Designed to work well with screen readers such as NVDA and JAWS.

---

## What is PowerShell?

PowerShell is a text-based tool built into Windows. Instead of clicking buttons and menus,
you type commands and press Enter. It can do things that normal Windows menus cannot do,
such as installing software quickly or changing system settings in bulk.

Think of it like a very powerful version of the Windows Run dialog, but smarter.

You do not need to learn programming to use it. This guide only uses copy-and-paste commands.

---

## Opening PowerShell

There are four ways to open PowerShell. Choose whichever works best for you.

---

### Method 1: Keyboard Shortcut (Recommended for Accessibility)

This method works without a mouse and is the fastest option.

To open PowerShell as Administrator (recommended for installing software):

1. Press and hold the Windows key, then press X. Release both keys.
   A small menu will appear or be announced by your screen reader.
2. Press A on your keyboard to select "Windows PowerShell (Admin)" or "Terminal (Admin)".
3. A security dialog will appear asking if you want to allow this app to make changes.
   Press Enter or click Yes.

To open regular PowerShell without Administrator rights (for everyday use):

1. Press and hold the Windows key, then press X. Release both keys.
2. Press I on your keyboard to select "Windows PowerShell" or "Terminal".

You will see a window with a blinking cursor. It is ready for you to type.

---

### Method 2: Start Menu Search (Works on Windows 10 and Windows 11)

This method is good if the keyboard shortcut above does not work on your machine.

1. Press the Windows key on your keyboard to open the Start menu.
2. Type the word: powershell
   You do not need to click anywhere first. Just start typing.
3. Search results will appear. Look for "Windows PowerShell" or "PowerShell".
4. To open it as Administrator, do one of the following:
   - If you have a mouse: right-click the result and choose "Run as administrator".
   - If you use a keyboard only: press the Tab key until "Run as administrator" is focused,
     then press Enter.
   - Shortcut method: when the result is highlighted, press Control, Shift, and Enter at
     the same time. This opens it as Administrator directly.
5. A security dialog will appear. Press Enter or click Yes to continue.

---

### Method 3: The Run Dialog

This method works on all versions of Windows, including older ones.

1. Press and hold the Windows key, then press R. Release both keys.
   The Run dialog box will open.
2. Type: powershell
3. To open as a regular user, press Enter.
   To open as Administrator, press Control, Shift, and Enter at the same time.
4. If a security dialog appears asking about changes, press Enter or click Yes.

---

### Method 4: Windows Terminal (Windows 11)

Windows 11 includes a newer app called Windows Terminal. It works the same as PowerShell
but has a more modern look.

1. Press and hold the Windows key, then press X.
2. Look for "Terminal (Admin)" in the list and press Enter on it.
3. Press Enter or click Yes on the security dialog.

If you see "Terminal" but not "Terminal (Admin)", select "Terminal" and then type your
commands without the Administrator option. Most agentic-brain setup steps still work.

---

## Running as Administrator: What It Means and Why It Matters

When you run PowerShell as Administrator, it has extra permissions to install software,
change system settings, and create files in protected folders.

For installing agentic-brain, Administrator access is recommended because the installer
needs to create folders and set up services on your computer.

When you open PowerShell as Administrator, Windows will show a User Account Control
prompt. This is a security check. It will ask:
"Do you want to allow this app to make changes to your device?"

You should click Yes or press Enter to continue. This is expected and safe.

If the UAC prompt does not appear and you are not sure whether you have Administrator
rights, look at the title bar of the PowerShell window. If it says "Administrator" at
the start of the title, you have Administrator rights.

---

## Execution Policy Explained

Windows has a security feature called Execution Policy. By default, it blocks scripts
from running. This prevents malicious scripts from running automatically. That is a
good thing in general.

However, to install agentic-brain, you need to allow scripts to run. The safest way
to do this is to allow only scripts that you have downloaded yourself (not scripts
that run automatically from the internet).

The command below sets the policy to "RemoteSigned". This means:
- Scripts you write yourself will run fine.
- Scripts you download will only run if they are signed by a trusted author,
  OR if you have explicitly chosen to run them.

This is safe. It does not turn off security. It just gives you control over what runs.

To set the execution policy, paste this command into PowerShell and press Enter:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

You may be asked: "Do you want to change the execution policy?"
Type Y and press Enter to confirm.

The "-Scope CurrentUser" part means this only applies to your user account. It does not
affect other users on the same computer.

---

## Installing Agentic Brain

Once PowerShell is open and the execution policy is set, you are ready to install.

Follow these steps one at a time. Copy each command exactly, paste it into PowerShell,
and press Enter. Wait for each command to finish before typing the next one.

A command is finished when you see a new line starting with "PS" followed by a folder
path, ending with a "greater than" symbol. For example:

```
PS C:\Users\YourName>
```

That prompt means PowerShell is ready for the next command.

### Step 1: Check that you have Node.js installed

Paste this and press Enter:

```
node --version
```

If you see a version number such as "v20.11.0", Node.js is installed. Continue to Step 3.

If you see an error saying the command was not found, go to Step 2.

### Step 2: Install Node.js (if needed)

Go to https://nodejs.org in your web browser.
Download the "LTS" version (Long Term Support). This is the stable, recommended version.
Run the installer and follow the on-screen steps. Accept the default options.
Once installed, close PowerShell and open it again. Then go back to Step 1 to confirm.

### Step 3: Run the agentic-brain installer

Paste this single command and press Enter:

```
irm https://raw.githubusercontent.com/agentic-brain/installer/main/install.ps1 | iex
```

This command downloads and runs the installer script. It may take several minutes.
You will see progress messages as it works.

If you are prompted to confirm anything during installation, read the message and
press Y then Enter to continue, or N then Enter to skip that step.

When the installer is done, it will tell you the next steps.

---

## Troubleshooting

### Error: "Running scripts is disabled on this system"

This means the execution policy has not been changed yet.
Run this command and try again:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Type Y and press Enter when asked to confirm.

---

### Error: "The term 'irm' is not recognized"

This means you are running an older version of PowerShell.
Run this command instead:

```
Invoke-RestMethod https://raw.githubusercontent.com/agentic-brain/installer/main/install.ps1 | Invoke-Expression
```

---

### Error: "Access is denied"

This usually means PowerShell is not running as Administrator.
Close PowerShell, open it again using Method 1 or Method 2 above (choosing the
Administrator option), and try the command again.

---

### Error: "node is not recognized as the name of a cmdlet"

Node.js is not installed or is not on your system PATH.
Follow Step 2 in the installation section above. After installing Node.js, close
PowerShell completely and open a new window before trying again.

---

### The window closed immediately

If PowerShell opened and then closed before you could read the error:

1. Open PowerShell normally (without the installer).
2. Then type or paste the command manually and press Enter.
   This way the window stays open so you can read any error messages.

---

### Nothing happens after pressing Enter

Check that the command was pasted completely. Sometimes long commands get cut off.
Try pasting the command in a plain text editor like Notepad first to check it looks
correct, then copy from there and paste into PowerShell.

---

### A red error message appeared

Read the first line of the error message. It usually tells you what went wrong.
Search for that error message in a web browser to find solutions, or refer to the
agentic-brain GitHub issues page for help.

---

## Screen Reader Tips

PowerShell works well with popular screen readers including NVDA and JAWS.

### General tips

- When you paste a command and press Enter, your screen reader will read the output
  line by line as it appears.
- If output is long, you can use your screen reader's review cursor to read back
  through previous lines.
- PowerShell uses plain text output, which screen readers handle reliably.
  There are no images or visual-only elements to worry about.

### Useful keyboard shortcuts inside PowerShell

- Up Arrow: repeat the previous command. Press it multiple times to go further back.
- Tab: auto-complete a command or filename. Press Tab again to cycle through options.
  This saves a lot of typing.
- Control + C: stop a running command. Use this if something is taking too long
  or you want to cancel.
- Control + A: select all text in the current line.
- Home: move to the start of the current line.
- End: move to the end of the current line.
- F7: show a list of recent commands in a pop-up box (classic PowerShell only,
  not Windows Terminal).

### Checking command output with NVDA

- After a command runs, press NVDA + Control + A to read new text that appeared
  on screen.
- Use NVDA's review mode (Numpad 7 and Numpad 9) to navigate up and down through
  previous output lines.

### Checking command output with JAWS

- JAWS reads PowerShell output automatically as it appears.
- Use the virtual cursor (Insert + Z) if you need to review what was printed.

### Windows Terminal and accessibility

Windows Terminal (the newer app) works well with screen readers but behaves slightly
differently from the classic PowerShell window. If your screen reader does not read
output automatically in Windows Terminal, check the accessibility settings in your
screen reader and ensure it is set to monitor terminal windows.

---

## Getting More Help

If you are stuck, here are some places to get help:

- Agentic Brain GitHub Issues: https://github.com/agentic-brain/agentic-brain/issues
- Windows PowerShell documentation: https://docs.microsoft.com/en-us/powershell/
- NVDA screen reader community: https://community.nvda-project.org/
- JAWS support: https://www.freedomscientific.com/support/

When asking for help, copy the exact error message you saw and include it in your
question. This helps others understand the problem quickly.

---

*Last updated: 2026*
*Part of the agentic-brain project documentation.*
*Accessibility feedback welcome via the GitHub issues page.*
