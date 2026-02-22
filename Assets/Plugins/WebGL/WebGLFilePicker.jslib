mergeInto(LibraryManager.library, {
    OpenFilePickerWebGL: function(objectNamePtr) {
        var objectName = UTF8ToString(objectNamePtr);
        var input = document.createElement('input');
        input.type = 'file';
        input.accept = '.glb,.gltf';
        input.style.display = 'none';
        document.body.appendChild(input);
        input.onchange = function(e) {
            var file = e.target.files[0];
            document.body.removeChild(input);
            if (!file) return;
            var reader = new FileReader();
            reader.onload = function(ev) {
                var buffer = ev.target.result;
                var bytes = new Uint8Array(buffer);
                var binary = '';
                var chunk = 8192;
                for (var i = 0; i < bytes.length; i += chunk) {
                    var slice = bytes.subarray(i, Math.min(i + chunk, bytes.length));
                    binary += String.fromCharCode.apply(null, slice);
                }
                var base64 = btoa(binary);
                var sent = false;
                if (typeof SendMessage === 'function') {
                    SendMessage(objectName, 'OnFilePickedBase64', base64);
                    sent = true;
                } else if (typeof Module !== 'undefined' && Module.SendMessage) {
                    Module.SendMessage(objectName, 'OnFilePickedBase64', base64);
                    sent = true;
                } else {
                    var inst = typeof unityInstance !== 'undefined' ? unityInstance : (typeof gameInstance !== 'undefined' ? gameInstance : null);
                    if (inst && typeof inst.SendMessage === 'function') {
                        inst.SendMessage(objectName, 'OnFilePickedBase64', base64);
                        sent = true;
                    }
                }
                if (!sent && typeof console !== 'undefined')
                    console.error('[WebGLFilePicker] SendMessage not found. Set window.unityInstance in your loader .then() after createUnityInstance.');
            };
            reader.readAsArrayBuffer(file);
        };
        input.click();
    },

    DownloadFileWebGL: function(filenamePtr, contentPtr) {
        var filename = UTF8ToString(filenamePtr);
        var content = UTF8ToString(contentPtr);
        if (!filename || content == null) return;
        var blob = new Blob([content], { type: 'application/octet-stream' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
});
