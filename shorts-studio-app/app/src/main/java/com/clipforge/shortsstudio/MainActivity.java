package com.clipforge.shortsstudio;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.os.Environment;
import android.view.View;
import android.widget.*;
import android.media.MediaMetadataRetriever;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.transformer.EditedMediaItem;
import androidx.media3.transformer.ExportException;
import androidx.media3.transformer.ExportResult;
import androidx.media3.transformer.Transformer;
import java.io.File;
import java.util.ArrayList;
import java.util.List;

/** Initial offline prototype. Exports sequential distinct source ranges; no AI scene scoring yet. */
public class MainActivity extends Activity {
  private static final int PICK_VIDEO=11;
  private Uri source;
  private TextView status;
  private EditText countInput;
  private int total, next;
  private long durationMs;
  private final List<long[]> segments = new ArrayList<>();
  private Transformer transformer;
  private File exportDir;
  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    LinearLayout root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(32,48,32,24);
    TextView title=new TextView(this); title.setText("SHORTS STUDIO • Offline beta");title.setTextSize(23);root.addView(title);
    Button pick=new Button(this);pick.setText("Choose source video");root.addView(pick);
    pick.setOnClickListener(v->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.setType("video/*");i.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,PICK_VIDEO);});
    countInput=new EditText(this);countInput.setInputType(2);countInput.setText("6");countInput.setHint("Number of unique Shorts");root.addView(countInput);
    Button render=new Button(this);render.setText("Export Shorts (30 sec each)");root.addView(render);
    status=new TextView(this);status.setText("Select a source video. Beta uses non-overlapping timeline clips.");root.addView(status);
    render.setOnClickListener(v->startExport());
    setContentView(root);
  }
  @Override protected void onActivityResult(int request,int result,Intent data){
    super.onActivityResult(request,result,data);
    if(request==PICK_VIDEO && result==RESULT_OK && data!=null){
      source=data.getData();
      try{getContentResolver().takePersistableUriPermission(source,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(Exception ignored){}
      status.setText("Selected: "+source);
    }
  }
  private void startExport(){
    if(source==null){status.setText("Choose a video first.");return;}
    try{
      total=Math.min(24,Math.max(1,Integer.parseInt(countInput.getText().toString())));
      MediaMetadataRetriever retriever=new MediaMetadataRetriever();
      retriever.setDataSource(this,source);
      durationMs=Long.parseLong(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
      retriever.release();
      segments.clear();
      long clip=30000;
      for(long start=0;start+clip<=durationMs && segments.size()<total;start+=clip)segments.add(new long[]{start,start+clip});
      if(segments.isEmpty()){status.setText("Source must be at least 30 seconds.");return;}
      exportDir=new File(getExternalFilesDir(Environment.DIRECTORY_MOVIES),"ShortsStudio");
      if(!exportDir.exists()&&!exportDir.mkdirs())throw new IllegalStateException("Output folder unavailable");
      transformer=new Transformer.Builder(this).setVideoMimeType(MimeTypes.VIDEO_H264).setAudioMimeType(MimeTypes.AUDIO_AAC).addListener(new Transformer.Listener(){
        @Override public void onCompleted(androidx.media3.common.Composition composition,ExportResult result){runOnUiThread(()->{next++;renderNext();});}
        @Override public void onError(androidx.media3.common.Composition composition,ExportResult result,ExportException error){runOnUiThread(()->status.setText("Export failed: "+error.getMessage()));}
      }).build();
      next=0;renderNext();
    }catch(Exception e){status.setText("Error: "+e.getMessage());}
  }
  private void renderNext(){
    if(next>=segments.size()){status.setText("Exported "+next+" Shorts to "+exportDir.getAbsolutePath());return;}
    long[] s=segments.get(next);
    MediaItem item=new MediaItem.Builder().setUri(source).setClippingConfiguration(new MediaItem.ClippingConfiguration.Builder().setStartPositionMs(s[0]).setEndPositionMs(s[1]).build()).build();
    EditedMediaItem edit=new EditedMediaItem.Builder(item).build();
    File file=new File(exportDir,String.format(java.util.Locale.US,"short_%03d.mp4",next+1));
    status.setText("Exporting "+(next+1)+"/"+segments.size()+"…");
    transformer.start(edit,file.getAbsolutePath());
  }
}
