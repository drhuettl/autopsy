 /*
 *
 * Autopsy Forensic Browser
 * 
 * Copyright 2012 42six Solutions.
 * Contact: aebadirad <at> 42six <dot> com
 * Project Contact/Architect: carrier <at> sleuthkit <dot> org
 * 
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 *     http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.sleuthkit.autopsy.report;

import java.io.File;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map.Entry;
import java.util.logging.Level;
import org.sleuthkit.autopsy.coreutils.Logger;
import java.util.regex.Pattern;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.commons.lang.StringEscapeUtils;
import org.w3c.dom.Element;
import org.w3c.dom.Document;
import org.w3c.dom.Comment;
import org.sleuthkit.autopsy.casemodule.Case;
import org.sleuthkit.autopsy.coreutils.XMLUtil;
import org.sleuthkit.autopsy.ingest.IngestManager;
import org.sleuthkit.datamodel.*;

/**
 * Generates an XML report for all the Blackboard Artifacts found in the current case.
 */
public class ReportXML implements ReportModule {

    public static Document xmldoc;
    private ReportConfiguration reportconfig;
    private String xmlPath;
    private static ReportXML instance = null;

    public ReportXML() {
    }

    public static synchronized ReportXML getDefault() {
        if (instance == null) {
            instance = new ReportXML();
        }
        return instance;
    }

    @Override
    public String generateReport(ReportConfiguration reportconfig) throws ReportModuleException {
        ReportGen reportobj = new ReportGen();
        reportobj.populateReport(reportconfig);
        HashMap<BlackboardArtifact, List<BlackboardAttribute>> report = reportobj.getResults();
        try {
            Case currentCase = Case.getCurrentCase(); // get the most updated case
            SleuthkitCase skCase = currentCase.getSleuthkitCase();
            String caseName = currentCase.getName();
            Integer imagecount = currentCase.getImageIDs().length;
            Integer filesystemcount = currentCase.getRootObjectsCount();
            Integer totalfiles = skCase.countFsContentType(TskData.TSK_FS_META_TYPE_ENUM.TSK_FS_META_TYPE_REG);
            Integer totaldirs = skCase.countFsContentType(TskData.TSK_FS_META_TYPE_ENUM.TSK_FS_META_TYPE_DIR);
            DocumentBuilder builder = DocumentBuilderFactory.newInstance().newDocumentBuilder();    
            Document ret = builder.newDocument();                                                   
            Element root = ret.createElement("Case");                                               
            DateFormat datetimeFormat = new SimpleDateFormat("yyyy/MM/dd HH:mm:ss");
            DateFormat dateFormat = new SimpleDateFormat("MM-dd-yyyy-HH-mm-ss");
            Date date = new Date();
            String datetime = datetimeFormat.format(date);
            String datenotime = dateFormat.format(date);
            Comment comment = ret.createComment("XML Report Generated by Autopsy 3 on " + datetime);    
            root.appendChild(comment);                                                                  
            //Create summary node involving how many of each type
            Element summary = ret.createElement("Summary");                                         
            if (IngestManager.getDefault().isIngestRunning()) {
                Element warning = ret.createElement("Warning");                                         
                warning.setTextContent("Report was run before ingest services completed!");             
                summary.appendChild(warning);                                                                     
            }
            Element name = ret.createElement("Name");                                                    
                    name.setTextContent(caseName);
                    summary.appendChild(name);
                    
            Element timages = ret.createElement("Total-Images");                                              
                    timages.setTextContent(imagecount.toString());
                    summary.appendChild(timages);
            
            Element tfilesys = ret.createElement("Total-FileSystems");                                   
                    tfilesys.setTextContent(filesystemcount.toString());
                    summary.appendChild(tfilesys);
            
            Element tfiles = ret.createElement("Total-Files");                                           
                    tfiles.setTextContent(totalfiles.toString());
                    summary.appendChild(tfiles);
            
            Element tdir = ret.createElement("Total-Directories");                                       
                    tdir.setTextContent(totaldirs.toString());
                    summary.appendChild(tdir);
                    
            root.appendChild(summary);
            //generate the nodes for each of the types so we can use them later
            
            Element nodeGen = ret.createElement("General-Information");                             
            Element nodeWebBookmark = ret.createElement("Web-Bookmarks");                           
            Element nodeWebCookie = ret.createElement("Web-Cookies");                               
            Element nodeWebHistory = ret.createElement("Web-History");                              
            Element nodeWebDownload = ret.createElement("Web-Downloads");                           
            Element nodeRecentObjects =ret.createElement("Recent-Documents");                       
            Element nodeTrackPoint = ret.createElement("Track-Points");                             
            Element nodeInstalled = ret.createElement("Installed-Programfiles");                    
            Element nodeKeyword = ret.createElement("Keyword-Search-Hits");                         
            Element nodeHash = ret.createElement("Hashset-Hits");                                   
            Element nodeDevice = ret.createElement("Attached-Devices");                             
            Element nodeEmail = ret.createElement("Email-Messages");                                
            Element nodeWebSearch = ret.createElement("Web-Search-Queries");                        
            Element nodeExif = ret.createElement("Exif-Metadata"); 
            
            //remove bytes
            Pattern INVALID_XML_CHARS = Pattern.compile("[^\\u0009\\u000A\\u000D\\u0020-\\uD7FF\\uE000-\\uFFFD\uD800\uDC00-\uDBFF\uDFFF]");
            for (Entry<BlackboardArtifact, List<BlackboardAttribute>> entry : report.entrySet()) {
                if (ReportFilter.cancel == true) {
                    break;
                }
                int cc = 0;
                Element artifact = ret.createElement("Artifact");
                Long objId = entry.getKey().getObjectID();
                Content cont = skCase.getContentById(objId);
                Long filesize = cont.getSize();
                try {
                    artifact.setAttribute("ID", objId.toString());
                    artifact.setAttribute("Name", cont.getName());
                    artifact.setAttribute("Size", filesize.toString());
                } catch (Exception e) {
                    Logger.getLogger(ReportXML.class.getName()).log(Level.WARNING, "Visitor content exception occurred:", e);
                }
                // Get all the attributes for this guy
                for (BlackboardAttribute tempatt : entry.getValue()) {
                    if (ReportFilter.cancel == true) {
                        break;
                    }
                    Element attribute = ret.createElement("Attribute");
                            attribute.setAttribute("Type", tempatt.getAttributeTypeDisplayName());
                    String tempvalue = tempatt.getValueString();
                    //INVALID_XML_CHARS.matcher(tempvalue).replaceAll("");
                    Element value = ret.createElement("Value");
                            value.setTextContent(StringEscapeUtils.escapeXml(tempvalue));
                    attribute.appendChild(value);        
                    Element context = ret.createElement("Context");
                            context.setTextContent(StringEscapeUtils.escapeXml(tempatt.getContext()));
                    attribute.appendChild(context);
                    artifact.appendChild(attribute);
                    cc++;
                }

                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_GEN_INFO.getTypeID()) {
                    //while (entry.getValue().iterator().hasNext())
                    // {
                    //  }
                    nodeGen.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_WEB_BOOKMARK.getTypeID()) {


                    nodeWebBookmark.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_WEB_COOKIE.getTypeID()) {

                    nodeWebCookie.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_WEB_HISTORY.getTypeID()) {

                    nodeWebHistory.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_WEB_DOWNLOAD.getTypeID()) {
                    nodeWebDownload.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_RECENT_OBJECT.getTypeID()) {
                    nodeRecentObjects.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_TRACKPOINT.getTypeID()) {
                    nodeTrackPoint.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_INSTALLED_PROG.getTypeID()) {
                    nodeInstalled.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_KEYWORD_HIT.getTypeID()) {
                    nodeKeyword.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_HASHSET_HIT.getTypeID()) {
                    nodeHash.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_DEVICE_ATTACHED.getTypeID()) {
                    nodeDevice.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_EMAIL_MSG.getTypeID()) {
                    nodeEmail.appendChild(artifact);
                }
                if (entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_WEB_SEARCH_QUERY.getTypeID()) {
                    nodeWebSearch.appendChild(artifact);
                }
                if(entry.getKey().getArtifactTypeID() == BlackboardArtifact.ARTIFACT_TYPE.TSK_METADATA_EXIF.getTypeID()){
                    nodeExif.appendChild(artifact);
                }
                

                //end of master loop
            }

            //add them in the order we want them to the document
            root.appendChild(nodeGen);
            root.appendChild(nodeWebBookmark);
            root.appendChild(nodeWebCookie);
            root.appendChild(nodeWebHistory);
            root.appendChild(nodeWebDownload);
            root.appendChild(nodeRecentObjects);
            root.appendChild(nodeTrackPoint);
            root.appendChild(nodeInstalled);
            root.appendChild(nodeKeyword);
            root.appendChild(nodeHash);
            root.appendChild(nodeDevice);
            root.appendChild(nodeEmail);
            root.appendChild(nodeWebSearch);
            root.appendChild(nodeExif);

            ret.appendChild(root);
            xmldoc = ret;

            //Export it the first time
            xmlPath = currentCase.getCaseDirectory() + File.separator + "Reports" + File.separator + caseName + "-" + datenotime + ".xml";
            this.save(xmlPath);

        } catch (Exception e) {
            Logger.getLogger(ReportXML.class.getName()).log(Level.WARNING, "Exception occurred", e);
        }

        return xmlPath;
    }

    @Override
    public void save(String path) {
        XMLUtil.saveDoc(ReportXML.class, xmlPath, "UTF-8", xmldoc);
    }

    @Override
    public String getName() {
        String name = "Default XML";
        return name;
    }

    @Override
    public String getReportType() {
        String type = "XML";
        return type;
    }
    
    @Override
    public String getExtension() {
        String ext = ".xml";
        return ext;
    }

    @Override
    public ReportConfiguration GetReportConfiguration() {
        ReportConfiguration config = reportconfig;
        return config;
    }

    @Override
    public void getPreview(String path) {
        BrowserControl.openUrl(path);
    }

    @Override
    public String getReportTypeDescription() {
        String desc = "This is an xml formatted report that is meant to be viewed in a modern browser.";
        return desc;
    }

    
}
