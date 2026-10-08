(function () {
    "use strict";
    window.AGW = window.AGW || {};

    // Minimal, dependency-free ZIP writer (STORE method, no compression).
    // Enough to bundle text files (HTML + a catalog snippet) into one .zip
    // the user can download and drop into their repo. Pure browser JS.

    let CRC_TABLE = null;
    function crcTable(){
        if (CRC_TABLE) return CRC_TABLE;
        const table = new Uint32Array(256);
        for (let n = 0; n < 256; n++){
            let c = n;
            for (let k = 0; k < 8; k++){
                c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
            }
            table[n] = c >>> 0;
        }
        CRC_TABLE = table;
        return table;
    }
    function crc32(bytes){
        const table = crcTable();
        let crc = 0xFFFFFFFF;
        for (let i = 0; i < bytes.length; i++){
            crc = (crc >>> 8) ^ table[(crc ^ bytes[i]) & 0xFF];
        }
        return (crc ^ 0xFFFFFFFF) >>> 0;
    }
    function strToUtf8(str){
        return new TextEncoder().encode(str);
    }
    function u16(n){ return [n & 0xFF, (n >>> 8) & 0xFF]; }
    function u32(n){ return [n & 0xFF, (n >>> 8) & 0xFF, (n >>> 16) & 0xFF, (n >>> 24) & 0xFF]; }

    // DOS date/time from a JS Date.
    function dosTime(d){
        const t = ((d.getHours() & 0x1F) << 11) | ((d.getMinutes() & 0x3F) << 5) | ((Math.floor(d.getSeconds() / 2)) & 0x1F);
        return t & 0xFFFF;
    }
    function dosDate(d){
        const dt = (((d.getFullYear() - 1980) & 0x7F) << 9) | (((d.getMonth() + 1) & 0x0F) << 5) | (d.getDate() & 0x1F);
        return dt & 0xFFFF;
    }

    // files: [{ name: "path/in/zip.txt", text: "..." }]
    function build(files){
        const now = new Date();
        const dtime = dosTime(now);
        const ddate = dosDate(now);
        const localParts = [];
        const central = [];
        let offset = 0;

        for (const file of files){
            const nameBytes = strToUtf8(file.name);
            const dataBytes = strToUtf8(file.text != null ? file.text : "");
            const crc = crc32(dataBytes);
            const size = dataBytes.length;

            // Local file header
            const local = [].concat(
                u32(0x04034b50),          // signature
                u16(20),                  // version needed
                u16(0x0800),              // flags: UTF-8 filename
                u16(0),                   // method: store
                u16(dtime), u16(ddate),   // mod time/date
                u32(crc),                 // crc32
                u32(size),                // compressed size
                u32(size),                // uncompressed size
                u16(nameBytes.length),    // filename length
                u16(0)                    // extra length
            );
            const localHeader = new Uint8Array(local);
            localParts.push(localHeader, nameBytes, dataBytes);

            // Central directory record
            const cen = [].concat(
                u32(0x02014b50),          // signature
                u16(20),                  // version made by
                u16(20),                  // version needed
                u16(0x0800),              // flags
                u16(0),                   // method
                u16(dtime), u16(ddate),
                u32(crc),
                u32(size),
                u32(size),
                u16(nameBytes.length),
                u16(0),                   // extra length
                u16(0),                   // comment length
                u16(0),                   // disk number start
                u16(0),                   // internal attrs
                u32(0),                   // external attrs
                u32(offset)               // local header offset
            );
            central.push({ header: new Uint8Array(cen), name: nameBytes });

            offset += localHeader.length + nameBytes.length + dataBytes.length;
        }

        // Assemble central directory
        const centralParts = [];
        let centralSize = 0;
        for (const c of central){
            centralParts.push(c.header, c.name);
            centralSize += c.header.length + c.name.length;
        }
        const centralOffset = offset;

        const end = new Uint8Array([].concat(
            u32(0x06054b50),              // EOCD signature
            u16(0), u16(0),               // disk numbers
            u16(central.length),          // entries on this disk
            u16(central.length),          // total entries
            u32(centralSize),             // central dir size
            u32(centralOffset),           // central dir offset
            u16(0)                        // comment length
        ));

        // Concatenate everything
        const chunks = localParts.concat(centralParts, [end]);
        let total = 0;
        for (const c of chunks) total += c.length;
        const out = new Uint8Array(total);
        let pos = 0;
        for (const c of chunks){ out.set(c, pos); pos += c.length; }
        return out;
    }

    function download(files, filename){
        const bytes = build(files);
        const blob = new Blob([bytes], { type: "application/zip" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename || "archive.zip";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    AGW.zip = { build, download, crc32 };
})();
