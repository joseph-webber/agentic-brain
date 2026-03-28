#import <Foundation/Foundation.h>
#import <CoreAudio/CoreAudio.h>

static NSString *ABCopyDeviceName(AudioDeviceID deviceID) {
    AudioObjectPropertyAddress address = {
        kAudioObjectPropertyName,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain,
    };
    CFStringRef name = NULL;
    UInt32 size = sizeof(name);
    OSStatus status = AudioObjectGetPropertyData(deviceID, &address, 0, NULL, &size, &name);
    if (status != noErr || name == NULL) {
        return nil;
    }
    return CFBridgingRelease(name);
}

static NSString *ABCopyDeviceUID(AudioDeviceID deviceID) {
    AudioObjectPropertyAddress address = {
        kAudioDevicePropertyDeviceUID,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain,
    };
    CFStringRef uid = NULL;
    UInt32 size = sizeof(uid);
    OSStatus status = AudioObjectGetPropertyData(deviceID, &address, 0, NULL, &size, &uid);
    if (status != noErr || uid == NULL) {
        return nil;
    }
    return CFBridgingRelease(uid);
}

static BOOL ABDeviceHasOutputStreams(AudioDeviceID deviceID) {
    AudioObjectPropertyAddress address = {
        kAudioDevicePropertyStreams,
        kAudioDevicePropertyScopeOutput,
        kAudioObjectPropertyElementMain,
    };
    UInt32 size = 0;
    return AudioObjectGetPropertyDataSize(deviceID, &address, 0, NULL, &size) == noErr && size > 0;
}

NSArray<NSDictionary *> *ABCopyOutputDevices(void) {
    AudioObjectPropertyAddress address = {
        kAudioHardwarePropertyDevices,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain,
    };
    UInt32 size = 0;
    if (AudioObjectGetPropertyDataSize(kAudioObjectSystemObject, &address, 0, NULL, &size) != noErr) {
        return @[];
    }

    UInt32 count = size / sizeof(AudioDeviceID);
    AudioDeviceID *deviceIDs = calloc(count, sizeof(AudioDeviceID));
    if (deviceIDs == NULL) {
        return @[];
    }

    NSMutableArray<NSDictionary *> *devices = [NSMutableArray array];
    if (AudioObjectGetPropertyData(kAudioObjectSystemObject, &address, 0, NULL, &size, deviceIDs) == noErr) {
        for (UInt32 index = 0; index < count; index++) {
            AudioDeviceID deviceID = deviceIDs[index];
            if (!ABDeviceHasOutputStreams(deviceID)) {
                continue;
            }
            NSString *name = ABCopyDeviceName(deviceID) ?: @"";
            NSString *uid = ABCopyDeviceUID(deviceID) ?: @"";
            [devices addObject:@{
                @"id": @(deviceID),
                @"name": name,
                @"uid": uid,
            }];
        }
    }

    free(deviceIDs);
    return devices;
}

NSString *ABCopyCurrentOutputDeviceUID(void) {
    AudioObjectPropertyAddress address = {
        kAudioHardwarePropertyDefaultOutputDevice,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain,
    };
    AudioDeviceID deviceID = 0;
    UInt32 size = sizeof(deviceID);
    if (AudioObjectGetPropertyData(kAudioObjectSystemObject, &address, 0, NULL, &size, &deviceID) != noErr) {
        return nil;
    }
    return ABCopyDeviceUID(deviceID);
}

NSString *ABCopyCurrentOutputDeviceName(void) {
    AudioObjectPropertyAddress address = {
        kAudioHardwarePropertyDefaultOutputDevice,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain,
    };
    AudioDeviceID deviceID = 0;
    UInt32 size = sizeof(deviceID);
    if (AudioObjectGetPropertyData(kAudioObjectSystemObject, &address, 0, NULL, &size, &deviceID) != noErr) {
        return nil;
    }
    return ABCopyDeviceName(deviceID);
}

BOOL ABSetDefaultOutputDeviceByID(AudioDeviceID deviceID) {
    AudioObjectPropertyAddress address = {
        kAudioHardwarePropertyDefaultOutputDevice,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain,
    };
    return AudioObjectSetPropertyData(kAudioObjectSystemObject, &address, 0, NULL, sizeof(deviceID), &deviceID) == noErr;
}

BOOL ABSetDefaultOutputDeviceByUID(NSString *uid) {
    for (NSDictionary *device in ABCopyOutputDevices()) {
        if ([device[@"uid"] isEqualToString:uid]) {
            return ABSetDefaultOutputDeviceByID((AudioDeviceID)[device[@"id"] unsignedIntValue]);
        }
    }
    return NO;
}

BOOL ABSetDefaultOutputDeviceByName(NSString *name) {
    for (NSDictionary *device in ABCopyOutputDevices()) {
        if ([device[@"name"] isEqualToString:name]) {
            return ABSetDefaultOutputDeviceByID((AudioDeviceID)[device[@"id"] unsignedIntValue]);
        }
    }
    return NO;
}

static NSData *ABJSONData(id object) {
    return [NSJSONSerialization dataWithJSONObject:object options:NSJSONWritingSortedKeys error:nil];
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        NSString *command = argc > 1 ? [NSString stringWithUTF8String:argv[1]] : @"status";
        id payload = @{};

        if ([command isEqualToString:@"list"]) {
            payload = @{ @"devices": ABCopyOutputDevices() };
        } else if ([command isEqualToString:@"current"]) {
            payload = @{
                @"name": ABCopyCurrentOutputDeviceName() ?: @"",
                @"uid": ABCopyCurrentOutputDeviceUID() ?: @"",
            };
        } else if ([command isEqualToString:@"set-name"] && argc > 2) {
            payload = @{ @"success": @(ABSetDefaultOutputDeviceByName([NSString stringWithUTF8String:argv[2]])) };
        } else if ([command isEqualToString:@"set-uid"] && argc > 2) {
            payload = @{ @"success": @(ABSetDefaultOutputDeviceByUID([NSString stringWithUTF8String:argv[2]])) };
        } else {
            payload = @{ @"success": @NO, @"error": @"unknown command" };
        }

        NSData *data = ABJSONData(payload);
        fwrite(data.bytes, 1, data.length, stdout);
    }
    return 0;
}
