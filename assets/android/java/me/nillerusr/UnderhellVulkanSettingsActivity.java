package me.nillerusr;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;

/** All controls are launcher-owned; no companion preferences or executable sdcard files. */
public final class UnderhellVulkanSettingsActivity extends Activity {
    private static final int PICK_DRIVER = 17321;
    private SharedPreferences prefs;
    private LinearLayout body;
    private Spinner driverSpinner;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private boolean importing;
    private void message(String text) {
        if (!isFinishing() && !isDestroyed()) new AlertDialog.Builder(this).setTitle("underhell / Vulkan")
            .setMessage(text).setPositiveButton(android.R.string.ok, null).show();
    }
    private TextView text(String value) {
        TextView view = new TextView(this); view.setText(value); view.setPadding(0, 12, 0, 12); body.addView(view); return view;
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setTitle("underhell — рендерер и GPU-драйверы");
        prefs = getSharedPreferences("mod", 0);
        ScrollView scroll = new ScrollView(this); body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL); body.setPadding(24, 16, 24, 24); scroll.addView(body); setContentView(scroll);
        text("GLES остаётся проверенным вариантом. DXVK-Sarek / Vulkan экспериментален: совместимость, изображение и скорость требуют проверки на устройстве. ASTC применяется только к GLES.");
        RadioGroup renderers = new RadioGroup(this);
        RadioButton gles = new RadioButton(this); gles.setId(1); gles.setText("GLES (TOGLES)"); renderers.addView(gles);
        RadioButton sarek = new RadioButton(this); sarek.setId(2); sarek.setText("Vulkan — DXVK-Sarek (Android 8+ / ARM64)"); renderers.addView(sarek);
        renderers.check(prefs.getString("underhell_renderer", "gles").equals("sarek") ? 2 : 1);
        renderers.setOnCheckedChangeListener((group, id) -> prefs.edit().putString("underhell_renderer", id == 2 ? "sarek" : "gles").apply());
        body.addView(renderers);
        text("Путь к ресурсам для встроенного Vulkan-запуска (корень с hl2/ и underhell/gameinfo.txt; регистр важен):");
        EditText path = new EditText(this); path.setSingleLine(true);
        path.setText(prefs.getString("underhell_gamepath", "/storage/emulated/0/srceng")); body.addView(path);
        Button save = new Button(this); save.setText("Сохранить путь"); body.addView(save);
        save.setOnClickListener(v -> { prefs.edit().putString("underhell_gamepath", path.getText().toString().trim()).apply(); message("Путь сохранён. Для GLES по-прежнему используются настройки Source Engine."); });
        text("Vulkan-драйвер (только для следующего полного запуска Sarek):");
        driverSpinner = new Spinner(this); body.addView(driverSpinner); reloadDrivers();
        text("ZIP должен содержать meta.json и ARM64 *.so в корне. Turnip предназначен для поддерживаемых Adreno, не для Mali. Системный Vulkan не требует ZIP. Пользовательские драйверы: Android 9+.");
        Button install = new Button(this); install.setText("Установить GPU-драйвер из ZIP…"); body.addView(install);
        install.setOnClickListener(v -> {
            if (importing) return;
            if (Build.VERSION.SDK_INT < 28) { message("libadrenotools требует Android 9 (API 28) или новее."); return; }
            new AlertDialog.Builder(this).setTitle("Доверяете источнику драйвера?")
                .setMessage("Это нативный код с правами приложения: он может читать игровые файлы и повредить данные. Проверка ZIP/ELF НЕ доказывает безопасность драйвера. Устанавливайте только из доверенного источника. Совместимость с GPU не гарантируется.")
                .setNegativeButton(android.R.string.cancel, null).setPositiveButton("Выбрать ZIP", (dialog, which) -> {
                    Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT); pick.setType("*/*");
                    pick.addCategory(Intent.CATEGORY_OPENABLE); pick.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    try { startActivityForResult(pick, PICK_DRIVER); } catch (Exception e) { message(e.toString()); }
                }).show();
        });
        Button revert = new Button(this); revert.setText("Вернуться на GLES + системный Vulkan"); body.addView(revert);
        revert.setOnClickListener(v -> { prefs.edit().putString("underhell_renderer", "gles").putString("underhell_driver", "").apply(); renderers.check(1); reloadDrivers(); });
        text("Переключение применяется после выхода из игры. Если Vulkan падает: вернитесь в этот лаунчер и выберите GLES. Не будет скрытой подмены выбранного ZIP системным драйвером.");
    }
    private void reloadDrivers() {
        try {
            List<UnderhellGpuDrivers.Driver> list = UnderhellGpuDrivers.installed(this);
            String selected = prefs.getString("underhell_driver", ""); int index = -1;
            for (int i = 0; i < list.size(); ++i) if (list.get(i).id.equals(selected)) index = i;
            if (index < 0) { index = list.size(); list.add(new UnderhellGpuDrivers.Driver(selected, "Недоступен: выберите другой драйвер", "", null)); }
            final List<UnderhellGpuDrivers.Driver> drivers = list;
            driverSpinner.setOnItemSelectedListener(null);
            driverSpinner.setAdapter(new ArrayAdapter<UnderhellGpuDrivers.Driver>(this, android.R.layout.simple_spinner_dropdown_item, list));
            driverSpinner.setSelection(index);
            driverSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
                public void onItemSelected(android.widget.AdapterView<?> parent, android.view.View view, int position, long id) {
                    prefs.edit().putString("underhell_driver", drivers.get(position).id).apply();
                }
                public void onNothingSelected(android.widget.AdapterView<?> parent) {}
            });
        } catch (Exception e) { message("Ошибка приватного хранилища драйверов: " + e); }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != PICK_DRIVER || result != RESULT_OK || data == null || data.getData() == null || importing) return;
        final Uri uri = data.getData(); importing = true;
        final ProgressDialog progress = ProgressDialog.show(this, "GPU-драйвер", "Проверка и установка ZIP…", true, false);
        worker.execute(() -> {
            try (InputStream input = getContentResolver().openInputStream(uri)) {
                if (input == null) throw new IOException("Document provider returned no stream");
                File installed = UnderhellDriverArchive.install(input, UnderhellGpuDrivers.root(this), dir -> UnderhellGpuDrivers.read(dir));
                UnderhellGpuDrivers.Driver driver = UnderhellGpuDrivers.read(installed);
                prefs.edit().putString("underhell_driver", driver.id).apply();
                runOnUiThread(() -> { importing = false; if (!isDestroyed()) { progress.dismiss(); reloadDrivers(); message("Установлен: " + driver.name + "\nБудет использован при следующем запуске Sarek. Это не проверка совместимости с GPU."); } });
            } catch (Exception e) {
                android.util.Log.e("UnderhellVulkan", "Driver ZIP rejected", e);
                runOnUiThread(() -> { importing = false; if (!isDestroyed()) { progress.dismiss(); message("Драйвер не установлен; предыдущий выбор сохранён.\n" + e); } });
            }
        });
    }
    @Override protected void onDestroy() { worker.shutdown(); super.onDestroy(); }
}
