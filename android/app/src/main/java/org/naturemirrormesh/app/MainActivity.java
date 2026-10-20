package org.naturemirrormesh.app;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;

/**
 * The entire native UI of Nature Mirror Mesh: one full-screen WebView
 * showing the Python app's own web UI (app/nmm_app.py) on
 * http://127.0.0.1:8899. All chat logic lives in Python; this activity
 * only boots the two Python processes and displays the UI.
 */
public class MainActivity extends Activity {
    private static final String TAG = "NMM";
    private static final String UI_URL = "http://127.0.0.1:8899";
    private static final int UI_PORT = 8899;

    private WebView webView;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int loadRetries = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        startPostOfficeService();
        startPythonApp();

        webView = new WebView(this);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                // The Python server takes a few seconds to come up; if a
                // load raced it, retry for a while instead of showing a
                // dead error page.
                if (request.isForMainFrame() && loadRetries < 40) {
                    loadRetries++;
                    handler.postDelayed(() -> view.loadUrl(UI_URL), 1500);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                loadRetries = 0;
            }
        });
        setContentView(webView);

        waitForServerThenLoad();
    }

    private void startPostOfficeService() {
        Intent intent = new Intent(this, PostOfficeService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }

    /** Runs nmm_app.py's server (via the Android launcher) in this process. */
    private void startPythonApp() {
        final String filesDir = getFilesDir().getAbsolutePath();
        Thread thread = new Thread(() -> {
            try {
                if (!Python.isStarted()) {
                    Python.start(new AndroidPlatform(this));
                }
                Python.getInstance()
                        .getModule("nmm_android_launcher")
                        .callAttr("start_app", filesDir);
                // start_app blocks for the life of the server.
            } catch (Throwable t) {
                Log.e(TAG, "Python app process failed", t);
            }
        }, "nmm-app-python");
        thread.start();
    }

    /** Polls the loopback UI port, then loads the UI once it answers. */
    private void waitForServerThenLoad() {
        Thread thread = new Thread(() -> {
            for (int i = 0; i < 120; i++) {
                try (Socket socket = new Socket()) {
                    socket.connect(new InetSocketAddress("127.0.0.1", UI_PORT), 500);
                    handler.post(() -> {
                        if (webView != null) {
                            webView.loadUrl(UI_URL);
                        }
                    });
                    return;
                } catch (IOException ignored) {
                    try {
                        Thread.sleep(1000);
                    } catch (InterruptedException e) {
                        return;
                    }
                }
            }
            // Give up polling; load anyway so the WebView error/retry
            // path (or a real error page) is what the user sees.
            handler.post(() -> {
                if (webView != null) {
                    webView.loadUrl(UI_URL);
                }
            });
        }, "nmm-ui-wait");
        thread.start();
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
