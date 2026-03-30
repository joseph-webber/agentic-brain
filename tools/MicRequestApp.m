#import <Cocoa/Cocoa.h>
#import <AVFoundation/AVFoundation.h>
#import <Python.h>

static NSString *const kAppName = @"MicRequestApp";
static NSString *const kStatusFileName = @"MicRequestApp.last_run.json";
static NSString *const kLogFileName = @"MicRequestApp.log";

static NSString *PyQuote(NSString *value) {
    NSMutableString *escaped = [value mutableCopy];
    [escaped replaceOccurrencesOfString:@"\\" withString:@"\\\\"
                                options:0
                                  range:NSMakeRange(0, escaped.length)];
    [escaped replaceOccurrencesOfString:@"'" withString:@"\\'"
                                options:0
                                  range:NSMakeRange(0, escaped.length)];
    [escaped replaceOccurrencesOfString:@"\n" withString:@"\\n"
                                options:0
                                  range:NSMakeRange(0, escaped.length)];
    return [NSString stringWithFormat:@"'%@'", escaped];
}

static NSString *JSONStringForObject(id object) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:object options:NSJSONWritingPrettyPrinted error:nil];
    return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
}

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) NSTextField *statusLabel;
@property(nonatomic, strong) NSTextField *detailLabel;
@property(nonatomic, strong) NSButton *openSettingsButton;
@property(nonatomic, strong) NSString *toolsDir;
@property(nonatomic, strong) NSString *agenticDir;
@property(nonatomic, strong) NSString *repoRoot;
@property(nonatomic, strong) NSString *scriptPath;
@property(nonatomic, strong) NSString *venvSitePackages;
@property(nonatomic, strong) NSString *venvPythonPath;
@property(nonatomic, strong) NSString *statusPath;
@property(nonatomic, strong) NSString *logPath;
@property(nonatomic, strong) NSArray<NSString *> *pythonArgs;
@property(nonatomic, assign) BOOL smokeTestMode;
@property(nonatomic, assign) BOOL pythonStarted;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [self resolvePaths];
    [self configureLogging];
    [self parseArguments];
    [self buildWindow];

    [NSApp activateIgnoringOtherApps:YES];
    [self.window makeKeyAndOrderFront:nil];

    [self logLaunchContext];
    [self writeStatus:@{
        @"mode": self.smokeTestMode ? @"smoke-test" : @"talk-to-karen",
        @"success": @NO,
        @"stage": @"app-started"
    }];
    [self refreshStatusAndContinue];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}

- (void)resolvePaths {
    NSString *bundlePath = NSBundle.mainBundle.bundlePath;
    self.toolsDir = [bundlePath stringByDeletingLastPathComponent];
    self.agenticDir = [self.toolsDir stringByDeletingLastPathComponent];
    self.repoRoot = [self.agenticDir stringByDeletingLastPathComponent];
    self.scriptPath = [self.agenticDir stringByAppendingPathComponent:@"talk_to_karen.py"];
    self.statusPath = [self.toolsDir stringByAppendingPathComponent:kStatusFileName];
    self.logPath = [self.toolsDir stringByAppendingPathComponent:kLogFileName];
    self.venvSitePackages = [self discoverVenvSitePackages];
    self.venvPythonPath = [self discoverVenvPythonPath];
}

- (NSString *)discoverVenvSitePackages {
    NSString *libDir = [[self.repoRoot stringByAppendingPathComponent:@"venv"] stringByAppendingPathComponent:@"lib"];
    NSArray<NSString *> *entries = [[NSFileManager defaultManager] contentsOfDirectoryAtPath:libDir error:nil];
    for (NSString *entry in entries) {
        if (![entry hasPrefix:@"python3."]) {
            continue;
        }
        NSString *candidate = [[[libDir stringByAppendingPathComponent:entry]
            stringByAppendingPathComponent:@"site-packages"] copy];
        BOOL isDir = NO;
        if ([[NSFileManager defaultManager] fileExistsAtPath:candidate isDirectory:&isDir] && isDir) {
            return candidate;
        }
    }
    return nil;
}

- (NSString *)discoverVenvPythonPath {
    NSArray<NSString *> *candidates = @[
        [[self.repoRoot stringByAppendingPathComponent:@"venv"] stringByAppendingPathComponent:@"bin/python3"],
        [[self.repoRoot stringByAppendingPathComponent:@"venv"] stringByAppendingPathComponent:@"bin/python"],
    ];
    NSFileManager *fm = [NSFileManager defaultManager];
    for (NSString *candidate in candidates) {
        if ([fm isExecutableFileAtPath:candidate]) {
            return candidate;
        }
    }
    return nil;
}

- (void)configureLogging {
    [[NSFileManager defaultManager] createFileAtPath:self.logPath contents:nil attributes:nil];
    freopen(self.logPath.fileSystemRepresentation, "a", stdout);
    freopen(self.logPath.fileSystemRepresentation, "a", stderr);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    printf("=== %s launched ===\n", kAppName.UTF8String);
}

- (void)parseArguments {
    NSMutableArray<NSString *> *pythonArgs = [NSMutableArray array];
    NSArray<NSString *> *args = NSProcessInfo.processInfo.arguments;
    for (NSUInteger i = 1; i < args.count; i++) {
        NSString *arg = args[i];
        if ([arg isEqualToString:@"--smoke-test"]) {
            self.smokeTestMode = YES;
        } else {
            [pythonArgs addObject:arg];
        }
    }
    self.pythonArgs = pythonArgs;
}

- (void)buildWindow {
    NSRect rect = NSMakeRect(0, 0, 540, 270);
    self.window = [[NSWindow alloc] initWithContentRect:rect
                                              styleMask:(NSWindowStyleMaskTitled |
                                                         NSWindowStyleMaskClosable |
                                                         NSWindowStyleMaskMiniaturizable)
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    self.window.title = @"Brain AI — MicRequestApp";
    [self.window center];
    self.window.releasedWhenClosed = NO;

    NSView *content = self.window.contentView;

    NSTextField *title = [self makeLabel:@"Microphone bridge for talk_to_karen.py" fontSize:20 bold:YES];
    title.frame = NSMakeRect(24, 208, 492, 28);
    title.alignment = NSTextAlignmentCenter;
    [content addSubview:title];

    self.statusLabel = [self makeLabel:@"Starting up…" fontSize:14 bold:NO];
    self.statusLabel.frame = NSMakeRect(24, 130, 492, 60);
    self.statusLabel.alignment = NSTextAlignmentCenter;
    self.statusLabel.maximumNumberOfLines = 4;
    [content addSubview:self.statusLabel];

    self.detailLabel = [self makeLabel:@"" fontSize:12 bold:NO];
    self.detailLabel.frame = NSMakeRect(24, 90, 492, 30);
    self.detailLabel.alignment = NSTextAlignmentCenter;
    self.detailLabel.maximumNumberOfLines = 2;
    self.detailLabel.textColor = NSColor.secondaryLabelColor;
    [content addSubview:self.detailLabel];

    self.openSettingsButton = [[NSButton alloc] initWithFrame:NSMakeRect(170, 28, 200, 34)];
    self.openSettingsButton.title = @"Open Privacy Settings";
    self.openSettingsButton.bezelStyle = NSBezelStyleRounded;
    self.openSettingsButton.target = self;
    self.openSettingsButton.action = @selector(openPrivacySettings);
    self.openSettingsButton.hidden = YES;
    [content addSubview:self.openSettingsButton];
}

- (NSTextField *)makeLabel:(NSString *)text fontSize:(CGFloat)fontSize bold:(BOOL)bold {
    NSTextField *label = [NSTextField labelWithString:text];
    label.font = bold ? [NSFont boldSystemFontOfSize:fontSize] : [NSFont systemFontOfSize:fontSize];
    label.editable = NO;
    label.bezeled = NO;
    label.drawsBackground = NO;
    return label;
}

- (void)refreshStatusAndContinue {
    AVAuthorizationStatus status = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio];
    switch (status) {
        case AVAuthorizationStatusAuthorized:
            [self updateStatus:@"✅ Microphone already authorised." detail:@"Launching embedded Python inside the app process." color:NSColor.systemGreenColor];
            [self startPythonIfNeeded];
            break;
        case AVAuthorizationStatusNotDetermined: {
            [self updateStatus:@"⏳ Asking macOS for microphone access…" detail:@"If a dialog appears, choose Allow." color:NSColor.labelColor];
            [AVCaptureDevice requestAccessForMediaType:AVMediaTypeAudio completionHandler:^(BOOL granted) {
                dispatch_async(dispatch_get_main_queue(), ^{
                    if (granted && [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeAudio] == AVAuthorizationStatusAuthorized) {
                        [self updateStatus:@"✅ Permission granted." detail:@"Launching talk_to_karen.py inside the app." color:NSColor.systemGreenColor];
                        [self startPythonIfNeeded];
                    } else {
                        [self handleRejectedPermission];
                    }
                });
            }];
            break;
        }
        case AVAuthorizationStatusDenied:
        case AVAuthorizationStatusRestricted:
            [self handleRejectedPermission];
            break;
    }
}

- (void)handleRejectedPermission {
    self.openSettingsButton.hidden = NO;
    [self updateStatus:@"⛔ Microphone access is not available." detail:@"Enable MicRequestApp in Privacy & Security → Microphone, then reopen it." color:NSColor.systemOrangeColor];
    [self writeStatus:@{
        @"mode": self.smokeTestMode ? @"smoke-test" : @"talk-to-karen",
        @"success": @NO,
        @"stage": @"permission-rejected"
    }];
}

- (void)updateStatus:(NSString *)status detail:(NSString *)detail color:(NSColor *)color {
    self.statusLabel.stringValue = status ?: @"";
    self.statusLabel.textColor = color ?: NSColor.labelColor;
    self.detailLabel.stringValue = detail ?: @"";
    printf("%s\n", status.UTF8String);
    if (detail.length > 0) {
        printf("%s\n", detail.UTF8String);
    }
}

- (void)openPrivacySettings {
    NSArray<NSString *> *urls = @[
        @"x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Microphone",
        @"x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    ];
    for (NSString *urlString in urls) {
        NSURL *url = [NSURL URLWithString:urlString];
        if (url && [[NSWorkspace sharedWorkspace] openURL:url]) {
            break;
        }
    }
}

- (void)startPythonIfNeeded {
    if (self.pythonStarted) {
        return;
    }
    self.pythonStarted = YES;
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        int exitCode = [self runEmbeddedPython];
        dispatch_async(dispatch_get_main_queue(), ^{
            if (self.smokeTestMode) {
                if (exitCode == 0) {
                    [self updateStatus:@"✅ Smoke test passed." detail:@"Python recorded live microphone audio inside the app process." color:NSColor.systemGreenColor];
                } else {
                    [self updateStatus:@"❌ Smoke test failed." detail:@"See MicRequestApp.log and MicRequestApp.last_run.json for details." color:NSColor.systemRedColor];
                }
                [NSApp terminate:nil];
            } else if (exitCode != 0) {
                [self updateStatus:@"❌ talk_to_karen.py failed to start." detail:@"See MicRequestApp.log for the embedded Python traceback." color:NSColor.systemRedColor];
                self.openSettingsButton.hidden = NO;
            } else {
                [NSApp terminate:nil];
            }
        });
    });
}

- (int)runEmbeddedPython {
    @autoreleasepool {
        NSString *mode = self.smokeTestMode ? @"smoke-test" : @"talk-to-karen";
        NSDictionary *config = @{
             @"mode": mode,
             @"repo_root": self.repoRoot ?: @"",
             @"agentic_dir": self.agenticDir ?: @"",
             @"script_path": self.scriptPath ?: @"",
             @"status_path": self.statusPath ?: @"",
             @"site_packages": self.venvSitePackages ?: @"",
             @"venv_python": self.venvPythonPath ?: @"",
             @"python_args": self.pythonArgs ?: @[],
         };

        NSString *configJSON = JSONStringForObject(config);
        NSString *pythonCode =
            [NSString stringWithFormat:
             @"import importlib.util, json, os, runpy, sys\n"
              "cfg = json.loads(%@)\n"
               "os.chdir(cfg['agentic_dir'])\n"
               "if cfg.get('site_packages'):\n"
               "    sys.path.insert(0, cfg['site_packages'])\n"
               "sys.path.insert(0, cfg['agentic_dir'])\n"
               "sys.path.insert(0, cfg['repo_root'])\n"
               "venv_python = cfg.get('venv_python') or ''\n"
               "if venv_python:\n"
               "    sys.executable = venv_python\n"
               "    os.environ['PYTHONEXECUTABLE'] = venv_python\n"
               "    os.environ.setdefault('__PYVENV_LAUNCHER__', venv_python)\n"
               "    try:\n"
               "        import multiprocessing\n"
               "        multiprocessing.set_executable(venv_python)\n"
               "    except Exception:\n"
               "        pass\n"
               "os.environ.setdefault('PYTHONUNBUFFERED', '1')\n"
               "status_path = cfg['status_path']\n"
               "def write_status(payload):\n"
              "    with open(status_path, 'w', encoding='utf-8') as fh:\n"
              "        json.dump(payload, fh, indent=2)\n"
              "        fh.write('\\n')\n"
              "if cfg['mode'] == 'smoke-test':\n"
              "    import numpy as np\n"
              "    import sounddevice as sd\n"
              "    device = None\n"
              "    for idx, dev in enumerate(sd.query_devices()):\n"
              "        if dev.get('max_input_channels', 0) > 0 and 'airpods' in dev['name'].lower():\n"
              "            device = idx\n"
              "            break\n"
              "    if device is None:\n"
              "        default_input = sd.default.device[0]\n"
              "        if default_input is not None and int(default_input) >= 0:\n"
              "            device = int(default_input)\n"
              "    if device is None:\n"
              "        raise RuntimeError('No input device available for smoke test')\n"
              "    info = sd.query_devices(device)\n"
              "    rate = int(info['default_samplerate'])\n"
              "    frames = int(rate * 0.75)\n"
              "    data = sd.rec(frames, samplerate=rate, channels=1, dtype='float32', device=device)\n"
              "    sd.wait()\n"
              "    peak = float(np.abs(data).max())\n"
              "    rms = float(np.sqrt(np.mean(np.square(data.astype('float64')))))\n"
              "    payload = {\n"
              "        'mode': 'smoke-test',\n"
              "        'success': peak > 1e-10,\n"
              "        'device_index': int(device),\n"
              "        'device_name': info['name'],\n"
              "        'sample_rate': rate,\n"
              "        'peak': peak,\n"
              "        'rms': rms,\n"
              "    }\n"
              "    write_status(payload)\n"
              "    print(json.dumps(payload, indent=2))\n"
              "    if not payload['success']:\n"
              "        raise SystemExit(2)\n"
              "else:\n"
              "    payload = {'mode': 'talk-to-karen', 'success': False, 'stage': 'python-starting'}\n"
              "    write_status(payload)\n"
              "    spec = importlib.util.spec_from_file_location('talk_to_karen_embedded', cfg['script_path'])\n"
              "    mod = importlib.util.module_from_spec(spec)\n"
              "    spec.loader.exec_module(mod)\n"
              "    sys.argv = [cfg['script_path'], *cfg.get('python_args', [])]\n"
              "    code = mod.main()\n"
              "    payload = {\n"
              "        'mode': 'talk-to-karen',\n"
              "        'success': code in (None, 0),\n"
              "        'exit_code': 0 if code is None else int(code),\n"
              "        'python_args': cfg.get('python_args', []),\n"
              "    }\n"
              "    write_status(payload)\n"
              "    if code not in (None, 0):\n"
              "        raise RuntimeError(f'talk_to_karen.main() returned {code}')\n",
             PyQuote(configJSON)];

        setenv("PYTHONUNBUFFERED", "1", 1);
        chdir(self.agenticDir.fileSystemRepresentation);

        Py_Initialize();
        int exitCode = PyRun_SimpleString(pythonCode.UTF8String);
        if (PyErr_Occurred()) {
            PyErr_Print();
            exitCode = 1;
        }
        Py_Finalize();
        return exitCode;
    }
}

- (void)writeStatus:(NSDictionary *)payload {
    NSData *data = [NSJSONSerialization dataWithJSONObject:payload options:NSJSONWritingPrettyPrinted error:nil];
    [data writeToFile:self.statusPath atomically:YES];
}

- (void)logLaunchContext {
    printf("Bundle ID: %s\n", (NSBundle.mainBundle.bundleIdentifier ?: @"missing-bundle-id").UTF8String);
    printf("Bundle path: %s\n", NSBundle.mainBundle.bundlePath.UTF8String);
    printf("Agentic dir: %s\n", self.agenticDir.UTF8String);
    printf("Script path: %s\n", self.scriptPath.UTF8String);
    printf("Site-packages: %s\n", (self.venvSitePackages ?: @"missing").UTF8String);
    printf("Venv python: %s\n", (self.venvPythonPath ?: @"missing").UTF8String);
    printf("Mode: %s\n", self.smokeTestMode ? "smoke-test" : "talk-to-karen");
}

@end

static BOOL IsPythonHelperInvocation(int argc, const char *argv[]) {
    if (argc < 2) {
        return NO;
    }
    return strcmp(argv[1], "-c") == 0 || strcmp(argv[1], "--multiprocessing-fork") == 0;
}

int main(int argc, const char *argv[]) {
    if (IsPythonHelperInvocation(argc, argv)) {
        char **pythonArgv = (char **)argv;
        setenv("PYTHONUNBUFFERED", "1", 1);
        return Py_BytesMain(argc, pythonArgv);
    }

    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        app.delegate = delegate;
        [app run];
    }
    return 0;
}
