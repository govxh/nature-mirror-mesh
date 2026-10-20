package org.naturemirrormesh.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/**
 * Hosts the LXMF propagation node ("post office") in its own Android
 * process (see AndroidManifest.xml: android:process=":postoffice").
 * It runs its own Chaquopy Python interpreter and its own Reticulum
 * instance from postoffice.py, with data under filesDir/nmm/postoffice —
 * fully separate from the app process, exactly as on the VM, where the
 * post office is a standalone process listening on 127.0.0.1:4429.
 *
 * It is a foreground service so Android does not kill it while the user
 * is relying on it to hold messages for offline contacts.
 */
public class PostOfficeService extends Service {
    private static final String TAG = "NMM-PostOffice";
    private static final String CHANNEL_ID = "nmm_postoffice";
    private static final int NOTIFICATION_ID = 1;

    @Override
    public void onCreate() {
        super.onCreate();
        startInForeground();
        startPythonPostOffice();
    }

    private void startInForeground() {
        NotificationManager manager =
                (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && manager != null) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    getString(R.string.postoffice_channel),
                    NotificationManager.IMPORTANCE_LOW);
            manager.createNotificationChannel(channel);
        }
        Notification notification = new Notification.Builder(this, CHANNEL_ID)
                .setContentTitle(getString(R.string.postoffice_notification_title))
                .setContentText(getString(R.string.postoffice_notification_text))
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setOngoing(true)
                .build();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void startPythonPostOffice() {
        final String filesDir = getFilesDir().getAbsolutePath();
        Thread thread = new Thread(() -> {
            try {
                if (!Python.isStarted()) {
                    Python.start(new AndroidPlatform(this));
                }
                Python.getInstance()
                        .getModule("nmm_android_launcher")
                        .callAttr("start_postoffice", filesDir);
                // start_postoffice blocks for the life of the node.
            } catch (Throwable t) {
                Log.e(TAG, "Post office process failed", t);
            }
        }, "nmm-postoffice-python");
        thread.start();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
