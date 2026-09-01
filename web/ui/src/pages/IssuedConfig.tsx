import { useEffect, useState } from "react";
import QRCode from "qrcode";

// The only moment this configuration exists anywhere: the private key was
// generated in this tab and is not stored by the panel. Closing the dialog
// loses it, and the only way back is to issue the profile again.
export function IssuedConfig({
  name,
  config,
  onClose,
}: {
  name: string;
  config: string;
  onClose: () => void;
}) {
  const [image, setImage] = useState("");

  useEffect(() => {
    void QRCode.toDataURL(config, { width: 320 }).then(setImage);
  }, [config]);

  function download() {
    const blob = new Blob([config], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${name}.conf`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="overlay">
      <div className="card wide">
        <h2>{name}</h2>
        <p className="warning">
          This is the only time this configuration can be taken. The private key
          was generated in your browser and the panel never saw it.
        </p>
        {image ? <img src={image} alt="configuration QR code" /> : null}
        <pre>{config}</pre>
        <div className="row">
          <button type="button" onClick={download}>
            Download .conf
          </button>
          <button type="button" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
