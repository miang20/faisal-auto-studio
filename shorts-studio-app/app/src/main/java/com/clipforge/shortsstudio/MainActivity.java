package com.clipforge.shortsstudio;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.os.Environment;
import android.graphics.Bitmap;
import android.media.MediaMetadataRetriever;
import android.widget.*;
import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.transformer.Effects;
import androidx.media3.effect.Presentation;
import androidx.media3.transformer.EditedMediaItem;
import androidx.media3.transformer.ExportException;
import androidx.media3.transformer.ExportResult;
import androidx.media3.transformer.Transformer;
import java.io.File;
import java.io.FileWriter;
import java.util.*;

/** Offline Shorts Studio beta: frame-change candidate selection, unique clips, vertical crop. */
public class MainActivity extends Activity {
  private static final int PICK_VIDEO=11;
  private Uri source;
  private TextView status;
  private EditText countInput, secondsInput;
  private int next;
  private final List<long[]> segments=new ArrayList<>();
  private Transformer transformer;
  private File exportDir;
  private volatile boolean analyzing=false;

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    LinearLayout root=new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(28,40,28,24);
    TextView title=new TextView(this);
    title.setText("SHORTS STUDIO  •  Offline Beta");
    title.setTextSize(22); root.addView(title);
    Button pick=new Button(this); pick.setText("1. Choose source video");root.addView(pick);
    pick.setOnClickListener(v->{Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.setType("video/*");i.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,PICK_VIDEO);});
    TextView hint=new TextView(this);hint.setText("Unique Shorts (1–24)");root.addView(hint);
    countInput=new EditText(this);countInput.setInputType(2);countInput.setText("12");root.addView(countInput);
    TextView duration=new TextView(this);duration.setText("Clip duration in seconds (15–60)");root.addView(duration);
    secondsInput=new EditText(this);secondsInput.setInputType(2);secondsInput.setText("30");root.addView(secondsInput);
    Button render=new Button(this);render.setText("2. Analyze and export vertical Shorts");root.addView(render);
    status=new TextView(this);status.setText("Choose a local video. Export requires free storage.");root.addView(status);
    render.setOnClickListener(v->startExport());
    setContentView(root);
  }

  @Override protected void onActivityResult(int request,int result,Intent data){
    super.onActivityResult(request,result,data);
    if(request==PICK_VIDEO&&result==RESULT_OK&&data!=null){
      source=data.getData();
      try{getContentResolver().takePersistableUriPermission(source,Intent.FLAG_GRANT_READ_URI_PERMISSION);}catch(Exception ignored){}
      status.setText("Source: "+source);
    }
  }

  private void startExport(){
    if(source==null){status.setText("Choose a source video first.");return;}
    if(analyzing){status.setText("Already analyzing.");return;}
    final int count,seconds;
    try{
      count=Math.max(1,Math.min(24,Integer.parseInt(countInput.getText().toString().trim())));
      seconds=Math.max(15,Math.min(60,Integer.parseInt(secondsInput.getText().toString().trim())));
    }catch(Exception e){status.setText("Enter valid numeric settings.");return;}
    analyzing=true;status.setText("Scanning full source for scene changes…");
    new Thread(()->{
      try{
        MediaMetadataRetriever retriever=new MediaMetadataRetriever();
        retriever.setDataSource(this,source);
        long durationMs=Long.parseLong(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
        List<long[]> chosen=selectClips(retriever,durationMs,seconds*1000L,count);
        retriever.release();
        runOnUiThread(()->{
          analyzing=false;
          if(chosen.isEmpty()){status.setText("Source is too short.");return;}
          segments.clear();segments.addAll(chosen);
          try{
            exportDir=new File(getExternalFilesDir(Environment.DIRECTORY_MOVIES),"ShortsStudio");
            if(!exportDir.exists()&&!exportDir.mkdirs())throw new IllegalStateException("Cannot create output directory");
            writeManifest();
            transformer=new Transformer.Builder(this)
              .setVideoMimeType(MimeTypes.VIDEO_H264)
              .setAudioMimeType(MimeTypes.AUDIO_AAC)
              .addListener(new Transformer.Listener(){
                @Override public void onCompleted(androidx.media3.common.Composition composition,ExportResult result){
                  runOnUiThread(()->{next++;renderNext();});
                }
                @Override public void onError(androidx.media3.common.Composition composition,ExportResult result,ExportException error){
                  runOnUiThread(()->status.setText("Export "+(next+1)+" failed: "+error.getMessage()));
                }
              }).build();
            next=0;renderNext();
          }catch(Exception e){status.setText("Export setup failed: "+e.getMessage());}
        });
      }catch(Exception e){runOnUiThread(()->{analyzing=false;status.setText("Analysis failed: "+e.getMessage());});}
    }).start();
  }

  /** Scan at 2s intervals and rank frame-change peaks. No overlap, no duplicated timeline. */
  private List<long[]> selectClips(MediaMetadataRetriever r,long duration,long clip,int limit){
    List<long[]> out=new ArrayList<>();
    if(duration<clip)return out;
    List<long[]> scores=new ArrayList<>();
    long prevHash=-1;
    for(long t=0;t<duration;t+=2000){
      Bitmap frame=null;
      try{frame=r.getFrameAtTime(t*1000,MediaMetadataRetriever.OPTION_CLOSEST_SYNC);}catch(Exception ignored){}
      if(frame==null)continue;
      long hash=frameHash(frame);
      frame.recycle();
      int difference=prevHash<0?0:Long.bitCount(hash^prevHash);
      prevHash=hash;
      long start=Math.max(0,Math.min(duration-clip,t-2000));
      scores.add(new long[]{start,difference});
    }
    scores.sort((a,b)->Long.compare(b[1],a[1]));
    for(long[] candidate:scores){
      if(out.size()>=limit)break;
      long start=candidate[0],end=start+clip;
      boolean overlap=false;
      for(long[] chosen:out){if(start<chosen[1]+1000 && end>chosen[0]-1000){overlap=true;break;}}
      if(!overlap)out.add(new long[]{start,end});
    }
    if(out.isEmpty())out.add(new long[]{0,clip});
    return out;
  }

  private long frameHash(Bitmap b){
    Bitmap scaled=Bitmap.createScaledBitmap(b,9,8,false);
    long hash=0;int bit=0;
    for(int y=0;y<8;y++)for(int x=0;x<8;x++){
      int a=scaled.getPixel(x,y),c=scaled.getPixel(x+1,y);
      int la=android.graphics.Color.red(a)+android.graphics.Color.green(a)+android.graphics.Color.blue(a);
      int lc=android.graphics.Color.red(c)+android.graphics.Color.green(c)+android.graphics.Color.blue(c);
      if(la>lc)hash|=1L<<bit;
      bit++;
    }
    scaled.recycle();return hash;
  }

  private void writeManifest(){
    try(FileWriter w=new FileWriter(new File(exportDir,"clips.csv"))){
      w.write("filename,source_start_ms,source_end_ms\n");
      for(int i=0;i<segments.size();i++)w.write(String.format(Locale.US,"short_%03d.mp4,%d,%d\n",i+1,segments.get(i)[0],segments.get(i)[1]));
    }catch(Exception ignored){}
  }

  private void renderNext(){
    if(next>=segments.size()){
      status.setText("Done: "+next+" unique timeline clips in "+exportDir.getAbsolutePath());
      return;
    }
    long[] s=segments.get(next);
    MediaItem item=new MediaItem.Builder().setUri(source)
      .setClippingConfiguration(new MediaItem.ClippingConfiguration.Builder()
      .setStartPositionMs(s[0]).setEndPositionMs(s[1]).build()).build();
    Effects effects=new Effects(Collections.emptyList(),Arrays.asList(
      Presentation.createForAspectRatio(9f/16f,Presentation.LAYOUT_SCALE_TO_FIT_WITH_CROP),
      Presentation.createForHeight(1920)));
    EditedMediaItem edit=new EditedMediaItem.Builder(item).setEffects(effects).build();
    File file=new File(exportDir,String.format(Locale.US,"short_%03d.mp4",next+1));
    if(file.exists()&&!file.delete()){status.setText("Cannot overwrite "+file.getName());return;}
    status.setText("Exporting vertical Short "+(next+1)+"/"+segments.size());
    try{transformer.start(edit,file.getAbsolutePath());}catch(Exception e){status.setText("Export failed: "+e.getMessage());}
  }
}
